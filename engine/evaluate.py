def evaluate(node, tags):

    # node: one JsonLogic-style expression tree, e.g. {"gt": [{"var": "x"}, 5]}
    # tags: the current world state - read here, only ever written by the scan cycle

    key = list(node.keys())[0]

    # ---------- BASE CASE ----------
    # the only node with nothing left to dig into - a direct lookup, no recursion

    if key == "var":
        value = node["var"]
        argument = tags[value]
        return argument

    # ---------- COMPARISON OPERATORS ----------
    # always exactly 2 elements - no loop, direct indexing

    if key == "gt":
        expression = node["gt"]
        #Now you have a list of 2 dictionaries
        first_element = expression[0]
        second_element = expression[1]
        if type(first_element) == dict:
            argument_first = evaluate(first_element, tags)
        else:
            argument_first = first_element

        if type(second_element) == dict:
            argument_second = evaluate(second_element, tags)
        else:
            argument_second = second_element

        argument = argument_first > argument_second
        return argument

    if key == "lt":
        expression = node["lt"]
        #Now you have a list of 2 dictionaries
        first_element = expression[0]
        second_element = expression[1]
        if type(first_element) == dict:
            argument_first = evaluate(first_element, tags)
        else:
            argument_first = first_element

        if type(second_element) == dict:
            argument_second = evaluate(second_element, tags)
        else:
            argument_second = second_element

        argument = argument_first < argument_second
        return argument

    if key == "ge":
        expression = node["ge"]
        #Now you have a list of 2 dictionaries
        first_element = expression[0]
        second_element = expression[1]
        if type(first_element) == dict:
            argument_first = evaluate(first_element, tags)
        else:
            argument_first = first_element

        if type(second_element) == dict:
            argument_second = evaluate(second_element, tags)
        else:
            argument_second = second_element

        argument = argument_first >= argument_second
        return argument

    if key == "le":
        expression = node["le"]
        #Now you have a list of 2 dictionaries
        first_element = expression[0]
        second_element = expression[1]
        if type(first_element) == dict:
            argument_first = evaluate(first_element, tags)
        else:
            argument_first = first_element

        if type(second_element) == dict:
            argument_second = evaluate(second_element, tags)
        else:
            argument_second = second_element

        argument = argument_first <= argument_second
        return argument

    if key == "eq":
        expression = node["eq"]
        #Now you have a list of 2 dictionaries
        first_element = expression[0]
        second_element = expression[1]
        if type(first_element) == dict:
            argument_first = evaluate(first_element, tags)
        else:
            argument_first = first_element

        if type(second_element) == dict:
            argument_second = evaluate(second_element, tags)
        else:
            argument_second = second_element

        argument = argument_first == argument_second
        return argument

    # ---------- BOOLEAN GATES ----------
    # unknown/variable length - loop + accumulator

    if key == "and":
        argument = True
        expression = node["and"]
        #expression = list
        for i in expression:
            #i = dictionaries or constant numbers or boolean constants - not assuming those right now
            argument = argument and evaluate(i, tags)
        return argument

    if key == "or":
        argument = False
        expression = node["or"]
        #expression = list
        for i in expression:
            #i = dictionaries or constant numbers or boolean constants - not assuming those right now
            argument = argument or evaluate(i, tags)
        return argument

    if key == "!":
        # only ever wraps ONE node, e.g. {"!": {"var": "StopBlockedRotor"}} - not a list at all
        argument = not evaluate(node["!"], tags)
        return argument

    #---------------------Conditional-------------
    if key == "if":
        expression = node["if"]
        #Expression = list of dictionaries
        first_argument = expression[0]
        first_value = expression[1]
        second_argument = expression[2]
        if evaluate(first_argument, tags) == True:
            if type(first_value) == dict:
                argument = evaluate(first_value, tags)
            else:
                argument = first_value
        else:
            if type(second_argument) == dict:
                argument = evaluate(second_argument, tags)
            else:
                argument = second_argument
        return argument

    # ---------- ARITHMETIC ----------
    # same 2-element dict-or-constant shape as the comparison operators above

    if key == "+":
        expression = node["+"]
        first_element = expression[0]
        second_element = expression[1]
        if type(first_element) == dict:
            argument_first = evaluate(first_element, tags)
        else:
            argument_first = first_element

        if type(second_element) == dict:
            argument_second = evaluate(second_element, tags)
        else:
            argument_second = second_element

        argument = argument_first + argument_second
        return argument

    if key == "-":
        expression = node["-"]
        first_element = expression[0]
        second_element = expression[1]
        if type(first_element) == dict:
            argument_first = evaluate(first_element, tags)
        else:
            argument_first = first_element

        if type(second_element) == dict:
            argument_second = evaluate(second_element, tags)
        else:
            argument_second = second_element

        argument = argument_first - argument_second
        return argument

    # ---------- SAFETY NET ----------
    # An unrecognized key fails loudly here instead of silently returning
    # None - a typo in the YAML should surface immediately, not show up
    # later as a mysteriously wrong or missing tag value.
    raise ValueError(f"evaluate(): unrecognized JsonLogic key '{key}' in node {node}")
