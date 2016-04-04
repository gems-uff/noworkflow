cdef class BaseLW:
    pass

cdef class ModuleLW(BaseLW):
    cdef public int trial_id, id;
    cdef public str name, path, version, code_hash;

cdef class DependencyLW(BaseLW):
    cdef public int trial_id, id, module_id;

cdef class EnvironmentAttrLW(BaseLW):
    cdef public int trial_id, id;
    cdef public str name, value;

cdef class DefinitionLW(BaseLW):
    cdef public int trial_id, id, parent, first_line, last_line;
    cdef public str namespace, name, type, code, code_hash, docstring;

cdef class ObjectLW(BaseLW):
    cdef public int trial_id, id, function_def_id;
    cdef public str name, type;

cdef class ActivationLW(BaseLW):
    cdef public int trial_id, id, line, caller_id, lasti;
    cdef public str definition_file, filename, name, return_value;
    cdef public object start, finish;
    cdef public list file_accesses, slice_stack, args, kwargs, starargs;
    cdef public list loops;
    cdef public list conditions;
    cdef public list permanent_conditions;
    cdef public dict context;
    cdef public bint with_definition, is_main, has_parameters;

cdef class ObjectValueLW(BaseLW):
    cdef public int trial_id, id, function_activation_id;
    cdef public str name, value, type;

cdef class FileAccessLw(BaseLW):
    cdef public int trial_id, id, function_activation_id;
    cdef public str name, mode, buffering;
    cdef public str content_hash_before, content_hash_after;
    cdef public object timestamp;
    cdef public bint done;

cdef class VariableLW(BaseLW):
    cdef public int trial_id, id, activation_id, line;
    cdef public str name, value, type;
    cdef public object time;

cdef class VariableDependencyLW(BaseLW):
    cdef public int trial_id, id;
    cdef public int source_activation_id, source_id;
    cdef public int target_activation_id, target_id;
    cdef public str type;

cdef class VariableUsageLW(BaseLW):
    cdef public int trial_id, id, activation_id, variable_id, line;
    cdef public str ctx;