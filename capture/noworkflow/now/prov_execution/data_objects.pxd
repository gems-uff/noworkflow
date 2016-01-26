cdef class BaseLW:
    pass

cdef class ActivationLW(BaseLW):
    cdef public int trial_id, id, line, caller_id, lasti;
    cdef public str name, return_value;
    cdef public object start, finish;
    cdef public list file_accesses, slice_stack, args, kwargs, starargs;
    cdef public dict context;


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
    cdef public str name, value;
    cdef public object time;

cdef class VariableDependencyLW(BaseLW):
    cdef public int trial_id, id;
    cdef public int dependent_activation, dependent;
    cdef public int supplier_activation, supplier;

cdef class VariableUsageLW(BaseLW):
    cdef public int trial_id, id, activation_id, variable_id, line;
    cdef public str name, ctx;