# elevator_viz.py
#
# Shared plotting/animation helpers for the elevator example. Deliberately
# NOT engine-generic (it knows what a floor, a door, and a call button are)
# -- but it IS stage-generic: everything here only ever reads tags out of
# a history dict keyed by tag name, and treats a missing key as "this stage
# doesn't have that" rather than an error. Concretely:
#   - Elevator_System_1's history has an integer-valued Current_Floor and
#     no Velocity_FloorsPerSec at all (no physics plant).
#   - Elevator_System_2's history has a continuous Current_Floor and a real
#     Velocity_FloorsPerSec.
# The same shaft schematic and playback code work for both, unmodified --
# that split is the whole point of building this once, here, instead of
# once per stage.
#
# animate_elevator(), render_static_frame(), and show_live() are purely
# passive: they take an already-finished history dict and display it, with
# no dependency on engine/ at all. run_interactive() is different -- it
# actually drives the simulation forward itself (imports run_scan from
# scan_cycle below), one scan per real timer tick, in response to floor and
# close-door buttons being clicked live. That's a real, deliberate coupling
# to the engine layer that the other three functions don't have -- a
# caller using run_interactive() needs engine/ on sys.path, the same way
# run_simulation.py already puts it there before importing this file.

import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle
from matplotlib.animation import FuncAnimation
from matplotlib.widgets import Slider, Button
from scan_cycle import run_scan

CAR_COLOR_CLOSED = "#4C72B0"
CAR_COLOR_OPEN = "#8CA6D6"
CALL_LIT = "#D62728"
CALL_UNLIT = "#BBBBBB"
FLOOR_LINE = "#888888"


def _floor_labels(top_floor, floor_labels=None):
    if floor_labels is not None:
        return floor_labels
    return ["G"] + [str(i) for i in range(1, int(top_floor) + 1)]


def _has_velocity(history):
    return "Velocity_FloorsPerSec" in history and len(history["Velocity_FloorsPerSec"]) > 0


def _has_monitoring(history):
    # True only for Elevator_System_3's history -- Systems 1/2 have
    # neither Damping_Ratio nor CUSUM_High at all, so this panel simply
    # doesn't exist for them, same graceful-degradation pattern as
    # _has_velocity above.
    return "Damping_Ratio" in history and "CUSUM_High" in history


def draw_shaft(ax, position, doors_open, calls_lit, top_floor, floor_labels=None):
    """
    Draws the shaft schematic at a single instant into an already-cleared
    Axes: floor lines, the car at `position` (any float in [0, top_floor],
    not just an integer -- this is what lets Elevator_System_2's continuous
    position show mid-flight, not just snap between floors), and one call
    light per floor.

    position    -- Current_Floor's value at this instant (int or float).
    doors_open  -- bool, this instant's Doors_Open.
    calls_lit   -- sequence of bool, one per floor (0 = ground), True means
                   that floor's call light is on. Caller decides what "lit"
                   means -- raw Call_FloorN (only true while physically
                   held) or Floor#_Request (true until served, the way a
                   real call button light actually behaves) both work here
                   the same way; this function just draws whatever it's given.
    top_floor   -- highest floor number.
    """
    labels = _floor_labels(top_floor, floor_labels)
    ax.set_xlim(0, 1.6)
    ax.set_ylim(-0.6, top_floor + 0.6)
    ax.set_xticks([])
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels)
    ax.set_title("Shaft")

    for floor_num in range(len(labels)):
        ax.axhline(floor_num, color=FLOOR_LINE, linewidth=1, linestyle="--", zorder=0)

    for floor_num, lit in enumerate(calls_lit):
        ax.add_patch(Circle((1.4, floor_num), 0.08,
                             color=CALL_LIT if lit else CALL_UNLIT, zorder=2))

    car_half_height = 0.32
    car_color = CAR_COLOR_OPEN if doors_open else CAR_COLOR_CLOSED
    ax.add_patch(Rectangle((0.15, position - car_half_height), 1.0, 2 * car_half_height,
                            facecolor=car_color, edgecolor="black", linewidth=1.2, zorder=1))

    if doors_open:
        # A visible gap in the car, rather than just a color change -- the
        # color alone doesn't read as "open" at a glance, especially in a
        # single static frame with no animation to imply motion.
        gap_width = 0.12
        ax.add_patch(Rectangle((0.15 + 0.5 - gap_width / 2, position - car_half_height),
                                gap_width, 2 * car_half_height,
                                facecolor="white", edgecolor="black", linewidth=0.8, zorder=2))


def draw_timeseries(ax_position, history, up_to_t, ax_velocity=None):
    """
    Draws the time-series panel(s) up through index up_to_t (inclusive),
    with a vertical marker at the current frame. Cropping to up_to_t is
    what lets this same function serve both a single static plot (pass
    len(history["t"]) - 1) and a live-updating animation frame (pass the
    current frame index).

    ax_velocity is optional -- pass it (and a history that actually has
    Velocity_FloorsPerSec) for Elevator_System_2; omit it for
    Elevator_System_1, where there's no velocity to show at all, not just
    a hidden/empty panel.
    """
    t = history["t"][:up_to_t + 1]
    position = history["Current_Floor"][:up_to_t + 1]

    ax_position.plot(t, position, color=CAR_COLOR_CLOSED, linewidth=1.6)
    ax_position.axvline(t[-1], color="black", linewidth=0.8, alpha=0.5)
    ax_position.set_ylabel("Current_Floor")
    ax_position.set_title("Position over time")

    if ax_velocity is not None and _has_velocity(history):
        velocity = history["Velocity_FloorsPerSec"][:up_to_t + 1]
        ax_velocity.plot(t, velocity, color="#C44E52", linewidth=1.6)
        ax_velocity.axvline(t[-1], color="black", linewidth=0.8, alpha=0.5)
        ax_velocity.set_ylabel("Velocity_FloorsPerSec")
        ax_velocity.set_xlabel("scan (t)")
        ax_velocity.set_title("Velocity over time")
    else:
        ax_position.set_xlabel("scan (t)")


def draw_monitoring_trend(ax_damping, ax_cusum, history, up_to_t):
    """
    Elevator_System_3-specific: a full-history trend of Damping_Ratio and
    CUSUM_High, deliberately NEVER windowed to "recent scans" the way
    draw_timeseries's position/velocity panels are -- the entire point is
    seeing a slow trend across potentially hundreds of scans, which a
    recent-window view would never show at all.

    ax_damping and ax_cusum must be a pre-existing twinx() pair, built
    ONCE by the caller (see _build_axes) and passed in every frame --
    calling .twinx() again on every redraw would silently accumulate a new
    overlapping axes each time instead of reusing one, since twinx()
    always creates a fresh axes object. This function only ever clears and
    redraws into the same two axes it's given.
    """
    t = history["t"][:up_to_t + 1]
    damping = history["Damping_Ratio"][:up_to_t + 1]
    cusum = history["CUSUM_High"][:up_to_t + 1]

    ax_damping.plot(t, damping, color="#55A868", linewidth=1.4)
    ax_damping.set_ylabel("Damping Ratio  (1.0 = healthy)", color="#55A868", fontsize=9)
    ax_damping.set_xlabel("scan (t)")
    ax_damping.set_title("Is the car quietly wearing out?\n(green = health, red = drift evidence)",
                          fontsize=9.5)
    ax_damping.tick_params(axis="y", labelcolor="#55A868")

    # ax_cusum is a twinx() pair created ONCE at setup -- .cla() (called
    # every frame, same as every other axes here) resets its tick/label
    # SIDE back to matplotlib's normal left-side default, silently undoing
    # the right-side placement twinx() only configures at creation time.
    # Confirmed by actually rendering a frame and seeing both labels
    # stacked on the left, overlapping -- not a hypothetical concern.
    # Re-applying the right-side placement every frame, not just once, is
    # the actual fix.
    ax_cusum.yaxis.tick_right()
    ax_cusum.yaxis.set_label_position("right")
    ax_cusum.plot(t, cusum, color="#C44E52", linewidth=1.4)
    ax_cusum.set_ylabel("CUSUM  (cumulative drift vs. healthy)", color="#C44E52", fontsize=9)
    ax_cusum.tick_params(axis="y", labelcolor="#C44E52")

    if "Threshold_H" in history and len(history["Threshold_H"]) > 0:
        ax_cusum.axhline(history["Threshold_H"][0], color="#C44E52", linewidth=1, linestyle="--", alpha=0.5)

    if "CUSUM_Alarm" in history:
        alarm_indices = [i for i, v in enumerate(history["CUSUM_Alarm"][:up_to_t + 1]) if v]
        if alarm_indices:
            ax_damping.axvline(alarm_indices[0], color="red", linewidth=1.3, alpha=0.7)


def _calls_at(history, t, call_keys):
    return [bool(history[key][t]) for key in call_keys if key in history]


def _format_command_actual(history, t):
    # The visible proof of the commanded/actual split described in
    # Elevator_System_2's description.md: Moving is what the logic
    # COMMANDS, Velocity_FloorsPerSec is what the physics plant ACTUALLY
    # produces. They always agree today -- the plant is perfectly obedient
    # -- but showing them as two separately-sourced numbers, side by side,
    # makes that independence visible now, before Elevator_System_3 ever
    # gives them a reason to disagree.
    #
    # Elevator_System_1's history has Moving but no Velocity_FloorsPerSec
    # at all -- there is no independently-produced "actual" signal to show,
    # because Current_Floor there IS the command (a CTUD counter the logic
    # drives itself). Saying so explicitly, rather than just omitting the
    # second half of the line, is the point: the absence itself is the
    # thing worth seeing.
    if "Moving" not in history:
        return ""
    commanded = f"Commanded (Moving): {bool(history['Moving'][t])}"
    if _has_velocity(history):
        actual = f"Actual (Velocity): {history['Velocity_FloorsPerSec'][t]:+.2f} floors/sec"
    else:
        actual = "Actual: no independent signal exists in this stage"
    return f"{commanded}    |    {actual}"


def _format_monitoring_readout(history, t):
    # A plain-language restatement of the monitoring panel's two numbers,
    # updated every frame -- the trend lines show the shape over time, this
    # shows what the car is doing RIGHT NOW in words, not just a colored
    # line and an axis label. Only produced for Elevator_System_3's
    # history (nothing calls this if _has_monitoring() is false).
    damping = history["Damping_Ratio"][t]
    cusum = history["CUSUM_High"][t]
    threshold = history["Threshold_H"][t] if "Threshold_H" in history else None

    if damping >= 0.75:
        wear_word = "healthy"
    elif damping >= 0.35:
        wear_word = "wearing"
    else:
        wear_word = "badly worn"

    line = f"Mechanical wear: {wear_word} (damping {damping:.2f}, 1.0 = new)"
    if threshold is not None:
        pct = min(100, 100 * cusum / threshold) if threshold > 0 else 0
        line += f"    |    Drift evidence: {cusum:.2f} of {threshold:.2f} needed to alarm ({pct:.0f}%)"
    else:
        line += f"    |    Drift evidence accumulated: {cusum:.2f}"
    return line


def _build_axes(has_velocity, has_monitoring=False, figsize_scale=1.0):
    # Shared by animate_elevator(), render_static_frame(), show_live(), and
    # run_interactive() -- all four want the identical panel layout,
    # differing only in what drives the frame index and what controls (if
    # any) sit below it. Always returns the same 7-tuple shape regardless
    # of which panels actually exist, with unused slots as None -- callers
    # never need to branch on how many values came back.
    if has_monitoring:
        fig, (ax_shaft, ax_pos, ax_vel, ax_monitor) = plt.subplots(
            1, 4, figsize=(15, 5 * figsize_scale), gridspec_kw={"width_ratios": [1, 1.2, 1.2, 1.3]})
        ax_monitor_twin = ax_monitor.twinx()  # created ONCE here -- see draw_monitoring_trend's docstring
    elif has_velocity:
        fig, (ax_shaft, ax_pos, ax_vel) = plt.subplots(
            1, 3, figsize=(11, 5 * figsize_scale), gridspec_kw={"width_ratios": [1, 1.4, 1.4]})
        ax_monitor, ax_monitor_twin = None, None
    else:
        fig, (ax_shaft, ax_pos) = plt.subplots(
            1, 2, figsize=(8, 5 * figsize_scale), gridspec_kw={"width_ratios": [1, 1.6]})
        ax_vel = None
        ax_monitor, ax_monitor_twin = None, None

    # One fig-level Text object for the commanded/actual readout, created
    # once and updated via set_text() every frame -- it lives above all
    # axes (figure-fraction coordinates, not tied to any Axes), so
    # ax.cla() calls in _render_frame never touch it.
    readout_text = fig.text(0.5, 0.94, "", ha="center", va="top", fontsize=9.5, family="monospace")
    return fig, ax_shaft, ax_pos, ax_vel, ax_monitor, ax_monitor_twin, readout_text


def _render_frame(ax_shaft, ax_pos, ax_vel, ax_monitor, ax_monitor_twin, readout_text,
                   history, t, top_floor, call_keys, floor_labels):
    # The one place that actually draws a single instant -- clears and
    # redraws all axes for index t. Every caller in this file that shows a
    # frame (whether once, on a timer, or on a slider drag) goes through
    # this exact function, so the panels can never visually drift apart
    # from each other between the different display modes.
    ax_shaft.cla()
    ax_pos.cla()
    if ax_vel is not None:
        ax_vel.cla()
    if ax_monitor is not None:
        ax_monitor.cla()
        ax_monitor_twin.cla()

    position = history["Current_Floor"][t]
    doors_open = bool(history["Doors_Open"][t]) if "Doors_Open" in history else False
    calls_lit = _calls_at(history, t, call_keys)

    draw_shaft(ax_shaft, position, doors_open, calls_lit, top_floor, floor_labels)
    draw_timeseries(ax_pos, history, t, ax_velocity=ax_vel)
    if ax_monitor is not None and _has_monitoring(history):
        draw_monitoring_trend(ax_monitor, ax_monitor_twin, history, t)

    if readout_text is not None:
        lines = [_format_command_actual(history, t)]
        if _has_monitoring(history):
            lines.append(_format_monitoring_readout(history, t))
        readout_text.set_text("\n".join(lines))


def animate_elevator(history, top_floor, call_keys=("Floor0_Request", "Floor1_Request", "Floor2_Request", "Floor3_Request", "Floor4_Request", "Floor5_Request"),
                      title="", interval_ms=150, floor_labels=None):
    """
    Builds a forward-only, non-interactive animation over the full history
    and returns (fig, anim) -- useful for saving a gif/mp4 (anim.save(path))
    rather than an interactive session. For actually looking at a run
    (scrub back and forth, pause, replay), use show_live() instead -- this
    function is kept for the export use case, not the day-to-day one.

    call_keys defaults to the Floor#_Request latches (lit until served),
    not the raw Call_FloorN buttons (lit only while held) -- that matches
    how a real elevator call button's light actually behaves, and both
    Elevator_System_1 and Elevator_System_2 already produce these tags
    unchanged from each other.
    """
    has_vel = _has_velocity(history)
    has_mon = _has_monitoring(history)
    fig, ax_shaft, ax_pos, ax_vel, ax_monitor, ax_monitor_twin, readout_text = _build_axes(has_vel, has_mon)
    fig.suptitle(title)

    def frame(t):
        _render_frame(ax_shaft, ax_pos, ax_vel, ax_monitor, ax_monitor_twin, readout_text,
                       history, t, top_floor, call_keys, floor_labels)
        fig.tight_layout(rect=[0, 0, 1, 0.86])

    anim = FuncAnimation(fig, frame, frames=len(history["t"]), interval=interval_ms, repeat=False)
    return fig, anim


def render_static_frame(history, t, top_floor, call_keys=("Floor0_Request", "Floor1_Request", "Floor2_Request", "Floor3_Request", "Floor4_Request", "Floor5_Request"),
                         title="", floor_labels=None):
    """
    Same visual as one animation frame, without building a FuncAnimation --
    useful for a single snapshot (a README screenshot, a quick sanity
    check) rather than the full playback.
    """
    has_vel = _has_velocity(history)
    has_mon = _has_monitoring(history)
    fig, ax_shaft, ax_pos, ax_vel, ax_monitor, ax_monitor_twin, readout_text = _build_axes(has_vel, has_mon)
    fig.suptitle(title)

    _render_frame(ax_shaft, ax_pos, ax_vel, ax_monitor, ax_monitor_twin, readout_text,
                  history, t, top_floor, call_keys, floor_labels)
    fig.tight_layout(rect=[0, 0, 1, 0.86])
    return fig


def run_interactive(operations, fb_instances, tags, top_floor, plant=None,
                     floor_labels=None, title="", scan_interval_ms=500,
                     call_floor_prefix="Call_Floor", request_prefix="Floor",
                     request_suffix="_Request", close_door_key="Close_Door_Button",
                     auto_cycle_floors=None, initial_speed=1):
    """
    Drives a live, real-time simulation the person actually controls --
    click a floor to call the car there, click Close Door to shortcut the
    hold. There is no precomputed history and no scripted scenario_fn:
    every scan is run for the first time the instant it happens, on a
    real timer, the same way a real PLC's scan cycle runs continuously
    against whatever the world is doing right now.

    operations, fb_instances, tags -- straight from
        engine/simulation_runner.setup_simulation(yaml_path), not yet run.
    top_floor  -- highest floor number; drives both the shaft's y-axis and
        how many floor-call buttons get drawn (0..top_floor).
    plant      -- optional physics plant; same role as in run_scan_loop().

    auto_cycle_floors -- optional list of floors (e.g. [0, 5]) an "Auto-
        Cycle" toggle button can call automatically, one after another,
        whenever the car is genuinely idle. OFF by default -- the person
        drives the car by clicking floor buttons, same as every other
        stage, until they choose to turn it on. Exists because
        Elevator_System_3's wear only becomes visible after dozens of
        round trips, and nobody should be forced to click a floor button
        90 times to see it -- but that's an option the person reaches for,
        not something running without being asked. A manual click always
        takes priority even with auto-cycle on: it only ever adds a call
        when there's genuinely nothing else going on.
    initial_speed -- how many scans run per timer tick, adjustable live via
        the 1x/5x buttons. Redraw happens once per tick regardless of
        speed, not once per scan -- decoupling how fast the simulation
        actually runs from how often the figure repaints is what makes 5x
        usable at all.

    One real subtlety this function handles, not the YAML: dispatch in
    every elevator_N.yaml file reads the raw Call_FloorN button directly,
    not a remembered latch (documented in Elevator_System_1's note 1) --
    a call has to still be held by the time the car is free to serve it.
    A single momentary click would frequently get missed. Rather than
    change that documented logic design, this function holds each clicked
    (or auto-cycled) floor's Call_FloorN true internally -- exactly
    emulating a person physically holding the button -- until
    Floor{N}_Request (which already exists, and already means "served or
    not") goes false again.
    """
    top_floor_int = int(top_floor)
    num_floors = top_floor_int + 1
    call_keys = tuple(f"{request_prefix}{n}{request_suffix}" for n in range(num_floors))
    labels = _floor_labels(top_floor_int, floor_labels)

    has_vel = "Velocity_FloorsPerSec" in tags
    has_mon = "Damping_Ratio" in tags and "CUSUM_High" in tags
    fig, ax_shaft, ax_pos, ax_vel, ax_monitor, ax_monitor_twin, readout_text = _build_axes(
        has_vel, has_mon, figsize_scale=1.15)
    fig.suptitle(title)
    plt.subplots_adjust(bottom=0.38, top=0.84)

    tracked_keys = list(tags.keys())
    history = {"t": []}
    for key in tracked_keys:
        history[key] = []

    ui_state = {"running": True, "pending_calls": set(), "close_door_armed": False,
                "speed": initial_speed, "auto_cycle_index": 0, "auto_cycle_enabled": False}

    def record():
        t = len(history["t"])
        history["t"].append(t)
        for key in tracked_keys:
            history[key].append(tags.get(key))

    def render_current():
        t = len(history["t"]) - 1
        _render_frame(ax_shaft, ax_pos, ax_vel, ax_monitor, ax_monitor_twin, readout_text,
                       history, t, top_floor_int, call_keys, floor_labels)
        fig.canvas.draw_idle()

    record()
    render_current()  # frame 0: the initial, pre-scan state

    def run_one_scan():
        if (auto_cycle_floors and ui_state["auto_cycle_enabled"]
                and not ui_state["pending_calls"] and not tags.get("Any_Pending", False)):
            next_floor = auto_cycle_floors[ui_state["auto_cycle_index"] % len(auto_cycle_floors)]
            ui_state["pending_calls"].add(next_floor)
            ui_state["auto_cycle_index"] += 1

        for n in range(num_floors):
            tags[f"{call_floor_prefix}{n}"] = n in ui_state["pending_calls"]
        tags[close_door_key] = ui_state["close_door_armed"]
        ui_state["close_door_armed"] = False  # momentary -- true for exactly this one scan

        run_scan(operations, fb_instances, tags)
        if plant is not None:
            plant.step(tags)

        # A held call is released once its floor's request has actually
        # been served -- not on click, and not just because the raw button
        # happened to read false this instant.
        served = {n for n in ui_state["pending_calls"] if not tags.get(f"{request_prefix}{n}{request_suffix}", False)}
        ui_state["pending_calls"].difference_update(served)

        record()

    def tick():
        if not ui_state["running"]:
            return
        for _ in range(ui_state["speed"]):
            run_one_scan()
        render_current()

    # --- Floor-call buttons, one per floor, laid out along the bottom ---
    floor_buttons = []

    def make_floor_handler(n):
        def handler(event):
            ui_state["pending_calls"].add(n)
        return handler

    button_width = min(0.9 / num_floors, 0.12)
    gap = 0.01
    start_x = 0.5 - (num_floors * button_width + (num_floors - 1) * gap) / 2
    for n in range(num_floors):
        ax_btn = fig.add_axes([start_x + n * (button_width + gap), 0.24, button_width, 0.06])
        btn = Button(ax_btn, labels[n])
        btn.on_clicked(make_floor_handler(n))
        floor_buttons.append(btn)  # keep references alive -- matplotlib drops handlers otherwise

    # --- Close-door and Play/Pause, second row ---
    def on_close_door_clicked(event):
        ui_state["close_door_armed"] = True

    ax_close = fig.add_axes([0.22, 0.15, 0.16, 0.06])
    close_button = Button(ax_close, "Close door")
    close_button.on_clicked(on_close_door_clicked)

    def on_play_clicked(event):
        ui_state["running"] = not ui_state["running"]
        play_button.label.set_text("Pause" if ui_state["running"] else "Resume")
    ax_play = fig.add_axes([0.42, 0.15, 0.16, 0.06])
    play_button = Button(ax_play, "Pause")
    play_button.on_clicked(on_play_clicked)

    # Auto-Cycle toggle -- only shown at all when the caller actually
    # passed floors to cycle between. OFF by default (see docstring): the
    # person clicks floor buttons themselves, same as every other stage,
    # unless they specifically choose to turn this on.
    if auto_cycle_floors:
        def on_auto_cycle_clicked(event):
            ui_state["auto_cycle_enabled"] = not ui_state["auto_cycle_enabled"]
            auto_cycle_button.label.set_text(
                "Auto-Cycle: On" if ui_state["auto_cycle_enabled"] else "Auto-Cycle: Off")
        ax_auto = fig.add_axes([0.62, 0.15, 0.18, 0.06])
        auto_cycle_button = Button(ax_auto, "Auto-Cycle: Off")
        auto_cycle_button.on_clicked(on_auto_cycle_clicked)

    # --- Speed buttons, third row -- decouples simulated scan rate from
    # redraw rate (see docstring). Capped at 5x, deliberately -- this is a
    # live simulation someone is watching and clicking buttons on, not a
    # batch job; 5x is enough to make a long run tolerable without making
    # it feel like the interaction has stopped being "live."
    speed_label = fig.text(0.5, 0.10, f"Speed: {initial_speed}x", ha="center", fontsize=9)
    speed_buttons = []

    def make_speed_handler(speed_value):
        def handler(event):
            ui_state["speed"] = speed_value
            speed_label.set_text(f"Speed: {speed_value}x")
        return handler

    speed_options = [1, 5]
    speed_button_width = 0.10
    speed_gap = 0.01
    speed_start_x = 0.5 - (len(speed_options) * speed_button_width + (len(speed_options) - 1) * speed_gap) / 2
    for i, sp in enumerate(speed_options):
        ax_sp = fig.add_axes([speed_start_x + i * (speed_button_width + speed_gap), 0.03, speed_button_width, 0.05])
        btn = Button(ax_sp, f"{sp}x")
        btn.on_clicked(make_speed_handler(sp))
        speed_buttons.append(btn)

    timer = fig.canvas.new_timer(interval=scan_interval_ms)
    timer.add_callback(tick)
    timer.start()

    plt.show()


def show_live(history, top_floor, call_keys=("Floor0_Request", "Floor1_Request", "Floor2_Request", "Floor3_Request", "Floor4_Request", "Floor5_Request"),
              title="", floor_labels=None, interval_ms=150):
    """
    Opens an interactive, scrubbable player over one simulation's history:
    a draggable slider covering every scan plus a Play/Pause button. This
    is the "engine" half of the split -- run_simulation.py's only job is
    to produce a history dict and call this once; everything about HOW
    that result is displayed and navigated (forward, backward, paused,
    mid-scrub) lives here, not scattered across every stage's own script.

    Calls plt.show() itself and blocks until the window is closed -- a
    caller doesn't do anything with a return value, the same way a caller
    doesn't manually drive a FuncAnimation's frames.
    """
    has_vel = _has_velocity(history)
    has_mon = _has_monitoring(history)
    fig, ax_shaft, ax_pos, ax_vel, ax_monitor, ax_monitor_twin, readout_text = _build_axes(has_vel, has_mon, figsize_scale=1.1)
    fig.suptitle(title)
    plt.subplots_adjust(bottom=0.22, top=0.84)

    num_frames = len(history["t"])
    state = {"frame": 0, "playing": False, "programmatic_update": False}

    def render(t):
        _render_frame(ax_shaft, ax_pos, ax_vel, ax_monitor, ax_monitor_twin, readout_text,
                       history, t, top_floor, call_keys, floor_labels)
        fig.canvas.draw_idle()

    render(0)

    ax_slider = fig.add_axes([0.15, 0.08, 0.55, 0.05])
    slider = Slider(ax_slider, "scan", 0, num_frames - 1, valinit=0, valstep=1)

    ax_play = fig.add_axes([0.74, 0.075, 0.10, 0.06])
    play_button = Button(ax_play, "Play")

    def on_slider_changed(val):
        state["frame"] = int(val)
        if not state["programmatic_update"]:
            # A real drag from the user, not the auto-advance timer below
            # moving the handle itself -- pause playback so it doesn't
            # immediately fight the position the user just chose.
            state["playing"] = False
            play_button.label.set_text("Play")
        render(state["frame"])
    slider.on_changed(on_slider_changed)

    def on_play_clicked(event):
        state["playing"] = not state["playing"]
        play_button.label.set_text("Pause" if state["playing"] else "Play")
    play_button.on_clicked(on_play_clicked)

    def advance():
        if not state["playing"]:
            return
        next_frame = (state["frame"] + 1) % num_frames
        # Move the slider programmatically, going through the same
        # on_slider_changed path a manual drag would -- one render path
        # for both, instead of a second copy of the render call here that
        # could quietly drift out of sync with the drag path over time.
        state["programmatic_update"] = True
        slider.set_val(next_frame)
        state["programmatic_update"] = False

    timer = fig.canvas.new_timer(interval=interval_ms)
    timer.add_callback(advance)
    timer.start()

    plt.show()