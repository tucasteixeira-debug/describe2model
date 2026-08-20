import yaml

from evaluate import evaluate
from function_blocks import R_TRIG, TON, RS, CTUD, PID


STATELESS_TYPES = ["and", "or", "!", "gt", "lt", "ge", "le", "eq", "if", "wiring", "+", "-"]
FB_CLASSES = {"TON": TON, "RS": RS, "CTUD": CTUD, "PID": PID, "R_TRIG": R_TRIG}


def load_data(yaml_path):
    with open(yaml_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
        # We get something like: operations = [{"name": "Startup_Button_Timer", "type": "TON" ....}]


def build_initial_tags(data):
    tags = {}
    placeholders = []

    for name, entry in data.get("physical_constants", {}).items():
        tags[name] = entry["value"]

    for name, entry in data.get("hmi_configuration", {}).items():
        default = entry.get("default")
        if default is not None:
            tags[name] = default
        else:
            # no default given in the YAML - fill a placeholder so the
            # engine can still run, but track it rather than pretend it's real
            tags[name] = False if entry.get("type") == "BOOL" else 0.0
            placeholders.append(name)

    for name, entry in data.get("runtime_inputs", {}).items():
        # dynamic, plant-side signals - everything starts off/zero;
        # a specific scenario overrides individual ones on top of this
        tags[name] = False if entry.get("type") == "BOOL" else 0.0

    # outputs: every tag an operation writes to (final or intermediate),
    # with no default at all - same as real PLC memory, everything starts
    # at 0/False the instant before scan 1 regardless of when it first runs
    for name, entry in data.get("outputs", {}).items():
        if name not in tags:
            tags[name] = False if entry.get("type") == "BOOL" else 0

    print(f"[init] {len(placeholders)} hmi_configuration tags had no confirmed "
          f"default and were filled with a placeholder (False/0.0): {placeholders[:8]}"
          f"{' ...' if len(placeholders) > 8 else ''}")

    return tags


def seed_operation_outputs(operations, tags):
    # Every operation's own output tag needs a starting value before scan 1,
    # same as real PLC memory - whether or not it's declared in the outputs
    # catalog (an intermediate tag can be real and simply never listed there).
    undeclared = []
    for op in operations:
        output = op["output"]
        if output not in tags:
            tags[output] = False
            undeclared.append(output)
    if undeclared:
        print(f"[init] {len(undeclared)} operation outputs were not in any "
              f"declared section (outputs:/hmi_configuration:/etc) - seeded "
              f"False as a starting value: {undeclared}")


def build_fb_instances(operations, scan_time=1):
    # scan_time defaults to 1 ("1 scan = 1 second"), unless a caller passes
    # a real interval. Every stateful block that tracks elapsed time (PID's
    # I/D terms, TON dwell timers) needs whatever interval you're actually
    # stepping the simulation at, or its internal clock runs too fast/slow
    # relative to wall-clock time.
    fb_instances = {}
    for op in operations:
        op_type = op["type"]
        if op_type == "TON" or op_type == "PID":
            fb_instances[op["name"]] = FB_CLASSES[op_type](scan_time=scan_time)
        elif op_type in FB_CLASSES:
            fb_instances[op["name"]] = FB_CLASSES[op_type]()
    return fb_instances


def run_scan(operations, fb_instances, tags):
    for op in operations:
        op_type = op["type"]
        if op_type in STATELESS_TYPES:
            result = evaluate(op["expression"], tags)
        else:
            instance = fb_instances[op["name"]]
            if op_type == "PID":
                result = instance.control_loop(op, tags)
            else:
                result = instance.check(op, tags)
        tags[op["output"]] = result
