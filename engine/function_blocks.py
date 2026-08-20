from evaluate import evaluate


class R_TRIG:
    def __init__(self):
        self.value = False  # nothing has triggered yet before scan 1

    def check(self, op, tags):
        new_value = evaluate(op["IN"], tags)
        if (self.value == False and new_value == True):
            argument = True
        else:
            argument = False
        self.value = new_value
        return argument


class TON:
    def __init__(self, scan_time=1):
        self.elapsed = 0            # accumulated time, starts at 0
        self.scan_time = scan_time  # real time per scan; defaults to 1 ("1 scan = 1 second")

    def check(self, op, tags):
        condition = evaluate(op["IN"], tags)
        preset = evaluate(op["PT"], tags)

        if condition:
            self.elapsed = self.elapsed + self.scan_time
        else:
            self.elapsed = 0

        argument = self.elapsed >= preset
        return argument


class RS:
    def __init__(self):
        self.value = False
        # Set is the "initializer" - you can't Reset something that was never
        # Set, but you can Set something that was never Reset - so it starts False.

    def check(self, op, tags):
        argument_set = False
        argument_reset = False

        for i in op["Set"]:
            if type(i) == dict:
                argument_set = argument_set or evaluate(i, tags)
            else:
                argument_set = argument_set or i

        for i in op["Reset"]:
            if type(i) == dict:
                argument_reset = argument_reset or evaluate(i, tags)
            else:
                argument_reset = argument_reset or i

        # Reset-dominant: Reset wins if both fire the same scan.
        if (argument_set == True and argument_reset == False):
            self.value = True
        elif (argument_reset == True):
            self.value = False
        # else: neither fired - self.value is simply left untouched,
        # which is exactly the "hold last value" behavior a latch needs.

        return self.value


class CTUD:
    def __init__(self):
        self.prev_cu = False
        self.prev_cd = False
        self.prev_r = False
        self.prev_ld = False
        self.counter = 0

    def check(self, op, tags):
        cu = evaluate(op["CU"], tags)
        cd = evaluate(op["CD"], tags)
        r = evaluate(op["R"], tags)
        ld = evaluate(op["LD"], tags)
        load_value = op["load_value"]   # a bare literal in the YAML, not a JsonLogic node
        pv = evaluate(op["PV"], tags)

        cu_edge = (self.prev_cu == False and cu == True)
        cd_edge = (self.prev_cd == False and cd == True)
        r_edge = (self.prev_r == False and r == True)
        ld_edge = (self.prev_ld == False and ld == True)

        # Precedence, per the vocabulary guide's open note: R beats LD beats CU/CD.
        if r_edge:
            self.counter = 0
        elif ld_edge:
            self.counter = load_value
        else:
            if cu_edge:
                self.counter = self.counter + 1
            if cd_edge:
                self.counter = self.counter - 1

        # clamp to [0, PV] - a counter should never exceed its configured
        # upper bound, nor go negative
        if self.counter > pv:
            self.counter = pv
        if self.counter < 0:
            self.counter = 0

        self.prev_cu = cu
        self.prev_cd = cd
        self.prev_r = r
        self.prev_ld = ld

        return self.counter


class PID:
    def __init__(self, scan_time=1):
        self.scan_time = scan_time
        self.value = 0
        self.error_accumulation = 0
        self.past_error = 0
        self.first_run = True
        self.p_term = 0
        self.i_term_scaled = 0
        self.d_term_scaled = 0

    def control_loop(self, op, tags):
        manual = evaluate(op["MANUAL"], tags)
        y_manual = evaluate(op["Y_MANUAL"], tags)

        if manual == True:
            # bypass entirely - integral/derivative memory stays untouched,
            # so the loop picks back up where it left off once MANUAL clears
            self.value = y_manual
            return self.value

        reset = evaluate(op["RESET"], tags)
        if reset == True:
            self.error_accumulation = 0
            self.first_run = True

        kp = evaluate(op["KP"], tags)
        tn = evaluate(op["TN"], tags)
        tv = evaluate(op["TV"], tags)
        y_min = evaluate(op["Y_MIN"], tags)
        y_max = evaluate(op["Y_MAX"], tags)
        set_point_value = evaluate(op["SET_POINT"], tags)
        actual_value = evaluate(op["ACTUAL"], tags)

        error = set_point_value - actual_value

        # Anti-windup here is back-calculation, not clamping. A simpler
        # scheme - freeze the integral while the output is saturated and the
        # error is still pushing the same direction, resume the instant it
        # reverses - only stops the integral from growing further. It does
        # nothing to shrink the (potentially huge) value it already built
        # up, so recovery after a long saturation is still slow.
        #
        # Back-calculation instead rewrites the integral accumulator every
        # saturated scan, to whatever value would make this scan's P+I+D sum
        # land exactly on the clamped output - not just pause it. Standard
        # tracking-based anti-windup (Åström & Hägglund), back-solved here
        # from this block's own Y = KP*(e + i_term + d_term) formula rather
        # than a separate tracking-gain parameterization, since that input
        # isn't exposed.
        #
        # In practice: integrate unconditionally every scan (the
        # back-calculation step below is what keeps it bounded, not a
        # freeze), compute the raw unclamped P+I+D sum, clamp it for the
        # output, and - only when clamping actually changed something -
        # back-solve the integral term to match, so next scan starts
        # consistent with what actually got delivered.
        self.error_accumulation = self.error_accumulation + error * self.scan_time
        i_term = self.error_accumulation / tn

        if self.first_run == True:
            d_term = 0
            self.first_run = False
        else:
            d_term = ((error - self.past_error) / self.scan_time) * tv

        self.past_error = error

        # KP scales the whole P+I+D sum, not just the P term - the standard
        # textbook formula (Y = KP*(e + I/TN + TV*de/dt)), and how most
        # stock industrial PID blocks are documented. Giving each term its
        # own independent gain instead is a common mistake, and gives a
        # different (wrong) result whenever KP != 1.
        y_unclamped = kp * (error + i_term + d_term)
        self.value = y_unclamped

        # hard clamp - never leave [Y_MIN, Y_MAX], regardless of what the raw
        # P+I+D sum comes out to
        if self.value > y_max:
            self.value = y_max
        if self.value < y_min:
            self.value = y_min

        # Only fires when clamping actually changed the output this scan.
        # Solves the same formula for the i_term that would make Y land
        # exactly on the clamped value, then writes error_accumulation back
        # out so next scan's integration starts consistent, not stale.
        # kp == 0 shouldn't happen (most PID blocks require KP != 0 to run
        # at all), but guarded rather than assumed.
        if self.value != y_unclamped and kp != 0:
            i_term = self.value / kp - error - d_term
            self.error_accumulation = i_term * tn

        # Kept around purely for plotting - the three terms already summed
        # to self.value above, this just exposes the breakdown (how much of
        # the output came from P vs I vs D), which the final number alone
        # can't show.
        self.p_term = kp * error
        self.i_term_scaled = kp * i_term
        self.d_term_scaled = kp * d_term

        return self.value
