# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Variable tagging"""
from __future__ import absolute_import, print_function, division, unicode_literals

from noworkflow.now.models.dependency_querier.querier_options import QuerierOptions
from noworkflow.now.models.dependency_querier import DependencyQuerier
from noworkflow.now.persistence.lightweight.stage_tags import StageTags
from noworkflow.now.persistence.models.base import proxy_gen
from noworkflow.now.persistence.models import Evaluation, CodeComponent
from noworkflow.now.persistence import relational

from typing import Dict, Optional, Tuple
from IPython.display import HTML
from pandas import DataFrame
import difflib
import numpy
import shelve
import textwrap


class NotebookQuerierOptions(QuerierOptions):
    """Navigation options object"""

    global body_function_def
    dep_list = []

    def __init__(self, level, *args, **kwargs):
        QuerierOptions.__init__(
            self, *args, **kwargs
        )  # change it to super when integrating in the main code
        self.level = level

    def visit_arrow(self, context, neighbor):
        """Navigate throught all evalutions getting operation and repr values"""

        if neighbor.evaluation.code_component.type == "function_def":
            body_function_def.append(int(neighbor.evaluation.code_component.id))

        arrow_list = ("argument", "<.__class__>", "item")
        type_list = (
            "add",
            "literal",
            "mult",
            "div",
            "param",
            "sub",
            "attribute",
            "usub",
            "function_def",
        )

        context_code_comp = context.evaluation.code_component
        neighbor_code_comp = neighbor.evaluation.code_component

        if context_code_comp.type == "literal" and neighbor_code_comp:
            self.dep_list.append((context_code_comp.name, context.evaluation.repr))
        elif neighbor.arrow not in arrow_list:
            if context_code_comp.type not in type_list:
                if neighbor_code_comp.type not in type_list:
                    if not (
                        neighbor.arrow == "use" and context_code_comp.type == "call"
                    ):
                        if neighbor_code_comp.container_id != None:
                            if (
                                neighbor_code_comp.container_id not in body_function_def
                                or self.level
                            ):
                                if (
                                    len(context.evaluation.repr) > 20
                                ):  # arbitrary lenght to avoid matricial outputs
                                    dimensions = numpy.frombuffer(
                                        context.evaluation.repr.encode(),
                                        dtype=numpy.uint8,
                                    )
                                    self.dep_list.append(
                                        (
                                            str(context_code_comp.name),
                                            str("matrix dim" + str(dimensions.shape)),
                                        )
                                    )
                                else:
                                    self.dep_list.append(
                                        (
                                            str(context_code_comp.name),
                                            str(context.evaluation.repr),
                                        )
                                    )

    def back_deps(self):
        """Creates a readable list of backward dependencies in a ordered dict format"""

        global dep_dict

        elements = [tuple_ for tuple_ in self.dep_list if tuple_[0] != tuple_[1]]
        filtered_list = [
            tup[0] for tup in zip(elements, [None] + elements) if tup[0] != tup[1]
        ]
        dep_dict = {i[0]: i[1] for i in reversed(list(enumerate(filtered_list)))}

        return dep_dict

    def global_back_deps(self):
        """Creates a readable list of backward dependencies from all steps in the current trial"""

        global global_dep_dict

        elements = [tuple_ for tuple_ in self.dep_list if tuple_[0] != tuple_[1]]
        filtered_list = [
            tup[0] for tup in zip(elements, [None] + elements) if tup[0] != tup[1]
        ]
        global_dep_dict = {i[0]: i[1] for i in reversed(list(enumerate(filtered_list)))}

        return global_dep_dict


def now_cell(tag):
    """
    Creates a tag in a notebook cell.

    Args:
        tag (str): The tag to associate with the notebook cell.

    Returns:
        None

    Example:
        >>> now_cell("feature_engineering")
    """

    trial_id = __noworkflow__.trial_id
    name = __noworkflow__.last_activation.name
    tag_name = str(tag)
    activation_id = __noworkflow__.last_activation.evaluation.activation_id

    # Writing it
    __noworkflow__.stage_tagss.add(trial_id, name, tag_name, activation_id)


def now_variable(var_name, value):
    """
    Creates a tag for a variable and associates a value with it.

    Args:
        var_name (str): The name of the variable.
        value (Any): The value to associate with the variable.

    Returns:
        Any: The value associated with the variable.

    Example:
        >>> x = now_variable("my_variable", 42)
        >>> x
        42
    """

    global tagged_var_dict

    dependencies = __noworkflow__.last_activation.dependencies[-1]
    dep_evaluation = dependencies.dependencies[-1].evaluation

    trial_id = dep_evaluation.trial_id
    name = str(var_name)
    activation_id = dep_evaluation.activation_id

    tagged_var_dict[name] = [dep_evaluation.id, value, activation_id, trial_id]

    print(dep_evaluation)
    # Writing it	  # Writing it
    __noworkflow__.stage_tagss.add(trial_id, name, value, activation_id)

    return value


def backward_deps(
    var_name: str, glanularity_level: Optional[bool] = False
) -> Dict[int, Tuple[str, str]]:
    """
    Navigate backward dependencies from a variable and
    return a dictionary of string tuples with pairs
    as variable/function and its associated value.

    Args:
        var_name (str): The name of the variable.
        granularity (bool, optional): The level of granularity
        for navigating dependencies. Default is False.

    Returns:
        Dict[str, Tuple[str, str]]: A dictionary where keys are
        variable or function names (strings) and values
        are tuples containing its attributed value (strings).

    Example:
        >>> dependencies = backward_deps("my_variable", True)
        >>> dependencies
        {'1': ('variable1', value1), '2': ('function1', value2), ...}
    """

    global tagged_var_dict
    global nbOptions
    global dep_dict

    trial_id = __noworkflow__.trial_id

    evals = list(
        proxy_gen(
            relational.session.query(Evaluation.m)
            .join(
                CodeComponent.m,
                (
                    (Evaluation.m.trial_id == CodeComponent.m.trial_id)
                    & (Evaluation.m.code_component_id == CodeComponent.m.id)
                ),
            )
            .filter(
                (CodeComponent.m.name == var_name)
                & (CodeComponent.m.trial_id == trial_id)
            )
        )
    )

    nbOptions = NotebookQuerierOptions(level=glanularity_level)
    querier = DependencyQuerier(options=nbOptions)
    _, _, _ = querier.navigate_dependencies([evals[-1]])

    return nbOptions.back_deps()


def global_backward_deps(
    var_name: str, glanularity_level: Optional[bool] = False
) -> Dict[int, Tuple[str, str]]:
    """
    Navigate backward dependencies from a variable and return
    all pre-dependencies associated with it in the
    current Trial.
    Returns a dictionary of string tuples where pairs are made
    of variable/function names and their
    associated values as strings.

    Args:
        var_name (str): The name of the variable.
        granularity (bool, optional): The level of granularity
        for navigating dependencies. Default is False.

    Returns:
        Dict[str, Tuple[str, str]]: A dictionary where keys are
        variable/function names (strings) and values
        are tuples containing the associated variable/function
        name and its associated value as strings.

    Example:
        >>> dependencies = global_backward_deps("my_variable", True)
        >>> dependencies
        {'1': ('variable1', 'value1'), '2': ('function1', 'value2'), ...}
    """

    trial_id = __noworkflow__.trial_id

    evals = list(
        proxy_gen(
            relational.session.query(Evaluation.m)
            .join(
                CodeComponent.m,
                (
                    (Evaluation.m.trial_id == CodeComponent.m.trial_id)
                    & (Evaluation.m.code_component_id == CodeComponent.m.id)
                ),
            )
            .filter(
                (CodeComponent.m.name == var_name)
                & (CodeComponent.m.trial_id == trial_id)
            )
        )
    )

    nbOptions = NotebookQuerierOptions(level=glanularity_level)
    querier = DependencyQuerier(options=nbOptions)
    _, _, _ = querier.navigate_dependencies(evals)

    return nbOptions.global_back_deps()


def store_operations(trial: str, ops_dict: dict) -> None:
    """
    Store dictionaries of dependencies in a shelve object.

    Args:
        trial (str): The trial identifier.
        ops_dict (dict): The dictionary of dependencies to store.

    Returns:
        None

    Example:
        >>> dependencies = {'variable1': ('function1', 'value1'), 'variable2': ('function2', 'value2'), ...}
        >>> store_operations("trial123", dependencies)
    """

    with shelve.open("ops") as shelf:
        shelf[trial] = ops_dict
        print("Dictionary stored in shelve.")


def dict_to_text(op_dict: dict) -> str:
    """
    Convert a dictionary format to plain text.

    Args:
        op_dict (dict): The dictionary to convert to plain text.

    Returns:
        str: The plain text representation of the dictionary.

    Example:
        >>> dependencies = {'variable1': ('function1', 'value1'),
        'variable2': ('function2', 'value2'), ...}
        >>> plain_text = dict_to_text(dependencies)
    """

    # Convert dictionary to plain text with
    # each key-value pair on a separate row
    plain_text = ""

    for key, value_list in op_dict.items():
        values_text = ", ".join(map(str, value_list))
        key_value_pair = f"{values_text}"
        wrapped_lines = textwrap.fill(key_value_pair, subsequent_indent="    ")
        plain_text += wrapped_lines + "\n"

    return plain_text


def trial_values_diff(trial_a, trial_b):
    """Compare values from two distinct trials"""

    comp_dict = {}
    # Retrieve the ops dictionary from the shelve file
    with shelve.open("ops") as shelf:
        dict1 = shelf[trial_a]
        dict2 = shelf[trial_b]

    if len(dict1) == len(dict2):
        for key in dict1:
            value1 = dict1[key]
            value2 = dict2[key]

            if isinstance(value1, numpy.ndarray) and isinstance(value2, numpy.ndarray):
                # If both values are NumPy arrays, compare if they are equal
                if numpy.array_equal(value1, value2):
                    comp_dict[value1[0]] = "equal matrices"
                else:
                    comp_dict[value1[0]] = "different matrices"

            elif value1 != value2:
                # If one or both values are scalars, compare their equality
                comp_dict[value1[0]] = "different values"
            else:
                comp_dict[value1[0]] = "equal values"

    return comp_dict


def trial_diff(trial_a: str, trial_b: str, raw: bool = False):
    """
    Visually compare two trials, but with limitations for
    complex types (matrices, tensors, etc).

    In these cases, it returns the dimension of the complex type.

    If the raw flag is set to True, it returns the raw HTML output.
    Otherwise, it displays the visual diff
    between the two trials in the cell.

    Args:
        trial_a (str): The identifier of the first trial.
        trial_b (str): The identifier of the second trial.
        raw (bool, optional): Whether to return the raw HTML
        output. Default is False.

    Returns:
        tuple or None: If raw is False, it returns None and displays
        the visual diff. If raw is True,
        it returns two dictionaries with pre-dependencies of both trials.

    Example:
        To display the visual diff in the cell:
        >>> trial_diff("trial123", "trial456")

        To obtain raw HTML output:
        >>> dict1, dict2 = trial_diff("trial123", "trial456", raw=True)
    """

    # Retrieve the ops dictionary from the shelve file
    with shelve.open("ops") as shelf:
        dict1 = shelf[trial_a]
        dict2 = shelf[trial_b]

    if raw:
        return dict1, dict2
    else:
        plain_text_a = dict_to_text(dict1)
        plain_text_b = dict_to_text(dict2)

        # Original and modified code strings
        original_code = plain_text_a
        modified_code = plain_text_b

        # Calculate the differences using difflib
        differ = difflib.HtmlDiff()
        diff_html = differ.make_table(
            original_code.splitlines(),
            modified_code.splitlines(),
            context=False,  # Show some context lines around changes
            numlines=0,  # Number of lines of context to show
        )

        # Add CSS styling for left alignment
        styled_diff_html = f"""
        <style>
        .diff_header {{
            background-color: #f1f1f1;
        }}
        .diff_next {{
            background-color: #f1f1f1;
        }}
        .diff_add {{
            background-color: #ddffdd;
        }}
        .diff_chg {{
            background-color: #ffffaa;
        }}
        .diff_sub {{
            background-color: #ffdddd;
        }}
        .diff_table {{
            text-align: left; /* Align the table content to the left */
        }}
        </style>
        {diff_html}
        """

        display(HTML(styled_diff_html))


def var_tag_diff(tag_name: str, pandas: bool = False):
    """
    Recollects all values associated with tag_name across distinct
    trials in the database.

    Args:
        tag_name (str): The name of the tag to retrieve values for.
        pandas (bool, optional): If True, returns a pandas DataFrame.
        If False, returns a list of lists.
        Default is False.

    Returns:
        pandas.DataFrame or list: If pandas is True, returns a pandas
        DataFrame with columns: 'trial_id',
        'short_trial_id', 'tag', 'value'.
        If pandas is False, returns a list of lists with the same information.

    Example:
        To retrieve values as a pandas DataFrame:
        >>> df = var_tag_diff("my_tag", pandas=True)

        To retrieve values as a list of lists:
        >>> values_list = var_tag_diff("my_tag")
    """

    access_list = list(
        proxy_gen(
            relational.session.query(StageTags.m).filter(StageTags.m.name == tag_name)
        )
    )

    values_list = []
    for i in access_list:
        values_list.append([i.trial_id, i.trial_id[-5:], i.name, float(i.tag_name)])

    if pandas:
        import pandas

        return pandas.DataFrame(
            values_list, columns=["trial_id", "short_trial_id", "tag", "value"]
        )
    else:
        return values_list


def var_tag_plot(tag_name: str):
    """
    Show a pyplot bar chart with the last 30 trial values of
    a tagged variable from the database.

    Args:
        tag_name (str): The name of the tag to retrieve values for.

    Returns:
        None

    Example:
        To create a bar chart for the 'my_tag' variable:
        >>> var_tag_plot("my_tag")
    """

    import pandas as pd
    import matplotlib.pyplot as plt

    access_list = list(
        proxy_gen(
            relational.session.query(StageTags.m).filter(StageTags.m.name == tag_name)
        )
    )

    values_list = []
    for i in access_list:
        values_list.append([i.trial_id, i.trial_id[-5:], i.name, float(i.tag_name)])

    df = pd.DataFrame(
        values_list, columns=["trial_id", "short_trial_id", "tag", "value"]
    )
    df = df.tail(30)  # arbitrary cuttoff for better chart visualization

    plt.bar(df.short_trial_id, df.value)
    plt.title(tag_name + " values")
    plt.xticks(rotation=90)

    plt.show()


def var_tag_values(tag_name: str) -> DataFrame:
    """
    Recollect all values attributed to tag_name
    variable across all trials in the database.

    Args:
        tag_name (str): The name of the tag variable to retrieve values for.

    Returns:
        DataFrame: A DataFrame containing the collected values with columns:
            - 'trial_id': The trial ID.
            - 'short_trial_id': A shortened version of the trial ID.
            - 'tag': The name of the tag.
            - 'value': The value attributed to the tag in float format.
    """

    access_list = list(
        proxy_gen(
            relational.session.query(StageTags.m).filter(StageTags.m.name == tag_name)
        )
    )

    if access_list == []:
        raise ValueError("No values found for tag " + tag_name)

    values_list = []
    for i in access_list:
        values_list.append([i.trial_id, i.trial_id[-5:], i.name, float(i.tag_name)])

    df = DataFrame(values_list, columns=["trial_id", "short_trial_id", "tag", "value"])
    return df


def resume_trials():
    """
    Resumes the list of trial ids available for comparison.

    Returns:
        list: A list of trial IDs available for comparison.
    """
    shelf = shelve.open("ops")
    list_id = list(shelf.keys())

    if list_id == []:
        raise ValueError("No trials found.")
    else:
        return list_id


def trial_intersection_diff(trial_a: str, trial_b: str) -> DataFrame:
    """
    Compare the common operations from two distinct trials.

    Args:
        trial_a (str): The identifier for the first trial.
        trial_b (str): The identifier for the second trial.

    Returns:
        pd.DataFrame: A DataFrame containing common operation details.

    Example:
        df = trial_intersection_diff('trial_12345', 'trial_67890')
    """

    # Retrieve the ops dictionary from the shelve file
    with shelve.open("ops") as shelf:
        dict1 = shelf[trial_a]
        dict2 = shelf[trial_b]

    # Extract relevant data from the dictionaries
    dict1 = {value[1][0]: value[1][1] for value in dict1.items()}
    dict2 = {value[1][0]: value[1][1] for value in dict2.items()}

    # Find the common keys
    common_keys = set(dict1.keys()) & set(dict2.keys())

    # Create a list of dictionaries with common key-value pairs
    common_data = [
        {"key": key, trial_a[-5:]: dict1[key], trial_b[-5:]: dict2[key]}
        for key in common_keys
    ]

    # Create a pandas DataFrame from the list of dictionaries
    df = DataFrame(common_data)

    return df
