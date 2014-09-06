package br.uff.ic.sel.noworkflow.controller;

import br.uff.ic.sel.noworkflow.model.Flow;
import br.uff.ic.sel.noworkflow.model.FunctionCall;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Timestamp;
import java.util.ArrayList;
import java.util.Collection;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public class SQLiteReader {

    private static final List<FunctionCall> callStack = new ArrayList<>();
    private final Map<String, FunctionCall> functionCalls = new LinkedHashMap<>();
    private final Map<String, Flow> flows = new LinkedHashMap<>();
    private PreparedStatement stmtObjectValue;
    private FunctionCall previousFunctionCall = null;

    public SQLiteReader(String path, int trialId) {
        try { // load the sqlite-JDBC driver using the current class loader
            Class.forName("org.sqlite.JDBC");
        } catch (ClassNotFoundException ex) {
            System.out.println("Could not load SQLite database driver.");
            System.exit(1);
        }

        try (Connection conn = DriverManager.getConnection("jdbc:sqlite:" + path)) {
            PreparedStatement stmtFunctionActivation = conn.prepareStatement("select * from function_activation where trial_id = ? order by start");
            stmtObjectValue = conn.prepareStatement("select * from object_value where function_activation_id = ? order by id");

            stmtFunctionActivation.setInt(1, trialId);
            ResultSet rs = stmtFunctionActivation.executeQuery();
            while (rs.next()) {
                
                updateCallStack(rs.getInt("caller_id"));

                // Add a flow from the previous to the current function
                FunctionCall currentFunctionCall = getFunctionCall(rs);
                if (previousFunctionCall != null) {
                    addFlow(previousFunctionCall, currentFunctionCall);
                }
                previousFunctionCall = currentFunctionCall;
            }

            // Pop the callstack adding RETURN edges
            while (!callStack.isEmpty()) {
                FunctionCall top = callStack.remove(callStack.size() - 1);
                addFlow(previousFunctionCall, top);
                previousFunctionCall = top;
            }
        } catch (SQLException e) {
            System.out.println("Error accessing database at " + path);
            e.printStackTrace();
        }
    }

    private void updateCallStack(int callerId) {
        if (previousFunctionCall != null && previousFunctionCall.hasActivation(callerId)) { // if this function call is in the scope of the previus function -> add the previous function to the call stack
            callStack.add(previousFunctionCall);
        } else if (!callStack.isEmpty()) { // if this function call is not in the scope of the top of the call stack -> pop the call stack
            FunctionCall top = callStack.get(callStack.size() - 1);
            while (!top.hasActivation(callerId)) { // while the top function of the callstack is not the one that called the current function, pop callstack              
                callStack.remove(callStack.size() - 1); // Remove the top function from call stack
                addFlow(previousFunctionCall, top); // Add a RETURN flow to the top function
                previousFunctionCall = top;
                top = callStack.get(callStack.size() - 1);
            }
        }
    }

    private FunctionCall getFunctionCall(ResultSet rs) throws SQLException {
        int callerId = rs.getInt("caller_id");
        int line = rs.getInt("line");
        String name = rs.getString("name");
        int id = rs.getInt("id");
        Map<String, String> arguments = getArguments(id);
        String returnValue = rs.getString("return");
        Timestamp start = Timestamp.valueOf(rs.getString("start"));
        Timestamp finish = Timestamp.valueOf(rs.getString("finish"));

        String key = getKey(line, name);
        FunctionCall functionCall = functionCalls.get(key);
        if (functionCall == null) {
            functionCall = new FunctionCall(callerId, line, name, id, arguments, returnValue, start, finish);
            functionCalls.put(key, functionCall);
        } else {
            functionCall.addActivation(id, arguments, returnValue, start, finish);
        }

        return functionCall;
    }
    
    private Map<String, String> getArguments(int functionCallId) throws SQLException {
        Map<String, String> arguments = new LinkedHashMap<>();

        stmtObjectValue.setInt(1, functionCallId);
        ResultSet rs = stmtObjectValue.executeQuery();
        while (rs.next()) {
            if ("ARGUMENT".equals(rs.getString("type"))) {
                arguments.put(rs.getString("name"), rs.getString("value"));
            }
        }

        return arguments;
    }

    private void addFlow(FunctionCall previous, FunctionCall current) {
        String key = getKey(previous.getLine(), previous.getName()) + " " + getKey(current.getLine(), current.getName());
        Flow flow = flows.get(key);
        if (flow == null) {
            if (previous.hasActivation(current.getCallerId())) { // previous function is the caller of the current function (CALL edge)
                flows.put(key, new Flow(previous, current, Flow.Type.CALL));
            } else if (previous.getCallerId() == current.getCallerId()) { // previous function and the current function were called in by the same function (SEQUENCE edge)
                flows.put(key, new Flow(previous, current, Flow.Type.SEQUENCE));
            } else if (current.hasActivation(previous.getCallerId())) { // current function is the caller of the previous function (RETURN edge)
                flows.put(key, new Flow(previous, current, Flow.Type.RETURN));
            } else {
                throw new RuntimeException("Unexpected flow from " + previous + " to " + current);
            }
        } else {
            flow.increaseTransitionCount();
        }
    }

    private String getKey(int line, String name) {
        StringBuilder stringBuilder = new StringBuilder();
        for (FunctionCall functionCall : callStack) {
            stringBuilder.append(functionCall.getLine()).append(" ").append(functionCall.getName()).append(" ");
        }
        stringBuilder.append(line).append(" ").append(name);
        return stringBuilder.toString();
    }

    public Collection<Flow> getFlows() {
        return flows.values();
    }

    public Collection<FunctionCall> getFunctionCalls() {
        return functionCalls.values();
    }
}
