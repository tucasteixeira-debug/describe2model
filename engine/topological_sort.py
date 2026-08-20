from graphlib import TopologicalSorter


# Walks one JsonLogic expression tree and returns every tag name referenced
# anywhere inside it, via {"var": ...} leaves.

def collect_vars(node):
    if type(node) != dict:
        # a bare constant (e.g. the "1" in {"+": [{"var": "count"}, 1]})
        # has no tags inside it - nothing to collect
        return []

    var_list = []
    key = list(node.keys())[0]
    value = node[key]

    if key in ["or", "and"]:
        for i in value:
            var_list = var_list + collect_vars(i)

    if key == "!":
        # only ever wraps one node, not a list - no loop needed
        var_list = var_list + collect_vars(value)

    if key in ["ge", "gt", "lt", "le", "eq", "+", "-"]:
        first_expression = value[0]
        second_expression = value[1]
        if type(first_expression) == dict:
            var_list = var_list + collect_vars(first_expression)
        if type(second_expression) == dict:
            var_list = var_list + collect_vars(second_expression)

    if key == "if":
        # condition, then_value, else_value - any of the three could be a
        # dict (recurse) or a bare constant (skip)
        for element in value:
            if type(element) == dict:
                var_list = var_list + collect_vars(element)

    if key == "var":
        if value not in var_list:
            var_list.append(value)

    return var_list


def build_output_lookout(operations):
    # output tag name -> operation name that produces it
    output_lookout = {}
    for i in operations:
        name = i["name"]
        output = i["output"]
        output_lookout[output] = name
    return output_lookout


def build_operation_lookout(operations):
    # operation name -> full operation dict
    operation_lookout = {}
    for i in operations:
        name = i["name"]
        operation_lookout[name] = i
    return operation_lookout


# Function blocks don't share one field name for their logic the way
# stateless ops do (those always have "expression"). TON/RS/CTUD/R_TRIG/PID
# each use their own named pins (IN/PT, Set/Reset, CU/CD/R/LD/PV, etc). So
# rather than assume a fixed field, walk every field on the operation except
# known metadata and collect whatever JsonLogic tree(s) are actually there -
# a single node, or a list of nodes (RS's Set/Reset are always lists, even
# with just one condition in them).

_METADATA_KEYS = ["name", "type", "output", "note", "source", "load_value"]


def collect_operation_vars(operation):
    var_list = []
    for key, value in operation.items():
        if key in _METADATA_KEYS:
            continue
        if type(value) == dict:
            var_list = var_list + collect_vars(value)
        elif type(value) == list:
            for item in value:
                if type(item) == dict:
                    var_list = var_list + collect_vars(item)
        # anything else (a bare number/bool) has no tags in it
    return var_list


def graph_builder(operations):
    # graph = {"OperationName": ["dependency_op_1", "dependency_op_2"], ...}
    graph = {}
    output_vars = build_output_lookout(operations)
    for operation in operations:
        name = operation["name"]
        dependencies = []
        input_vars = collect_operation_vars(operation)
        for var in input_vars:
            if var in output_vars:
                producer = output_vars[var]
                if producer == name:
                    # an operation reading its own output tag isn't a
                    # same-scan ordering requirement - it's reading last
                    # scan's held value, same idea as self.value/self.elapsed
                    # inside the function-block classes. Not a real
                    # dependency edge; treating it as one would make every
                    # self-referencing timer or latch an unsolvable cycle.
                    continue
                dependencies.append(producer)
        graph[name] = dependencies

    return graph


def topological_sorter(graph):
    ts = TopologicalSorter(graph)
    order = list(ts.static_order())
    return order
