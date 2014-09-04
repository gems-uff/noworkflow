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
    private static List<FunctionCall> callStack = new ArrayList<>();
    private Map<String, FunctionCall> functionCalls = new LinkedHashMap<>();
    private Map<String, Flow> flows = new LinkedHashMap<>(); 
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
            PreparedStatement stmtFunctionActivation = conn.prepareStatement("select * from function_activation where trial_id = ? order by id");
            stmtObjectValue = conn.prepareStatement("select * from object_value where function_activation_id = ? order by id");

            stmtFunctionActivation.setInt(1, trialId);
            ResultSet rs = stmtFunctionActivation.executeQuery();
            while (rs.next()) {
                FunctionCall currentFunctionCall = getFunctionCall(rs);
                if (previousFunctionCall != null) {
                    addFlow(previousFunctionCall, currentFunctionCall);
                }
                previousFunctionCall = currentFunctionCall;
            }
            for (int i = callStack.size() - 1;i >= 0; i--) {
                FunctionCall top = callStack.get(i);
                addFlow(previousFunctionCall, top);
                previousFunctionCall = top;
            }
        } catch (SQLException e) {
            System.out.println("Error accessing database at " + path);
            e.printStackTrace();
        }
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

    private FunctionCall getFunctionCall(ResultSet rs) throws SQLException {
        int callerId = rs.getInt("caller_id");
        int line = rs.getInt("line");
        String name = rs.getString("name");
        int id = rs.getInt("id");
        Map<String, String> arguments = getArguments(id);
        String returnValue = rs.getString("return");
        Timestamp start = Timestamp.valueOf(rs.getString("start"));
        Timestamp finish = Timestamp.valueOf(rs.getString("finish"));

        String key = line + " " + name;
        FunctionCall functionCall = functionCalls.get(key);
        if (functionCall == null) {
            functionCall = new FunctionCall(callerId, line, name, id, arguments, returnValue, start, finish);
            functionCalls.put(key, functionCall);
        } else {
            functionCall.addActivation(id, arguments, returnValue, start, finish);
        }
        
        return functionCall;
    }

    private void addFlow(FunctionCall source, FunctionCall target) {
        String key = source.getLine() + " " + source.getName() + " " + target.getLine() + " " + target.getName();
        Flow flow = flows.get(key);
        if (flow == null) {
            if (source.hasActivation(target.getCallerId())) {
                flows.put(key, new Flow(source, target, Flow.Type.CALL));
                callStack.add(source);
            } else if (source.getCallerId() == target.getCallerId()) {
                flows.put(key, new Flow(source, target, Flow.Type.SEQUENCE));
            } else if (target.hasActivation(source.getCallerId())) {
                flows.put(key, new Flow(source, target, Flow.Type.RETURN));
                callStack.remove(callStack.size() - 1);
            } else {  // Situation where the source is the last method activation of top (parent) and target is a method in the sequence of top (A -> top -> source and A -> target).
                FunctionCall top = callStack.get(callStack.size() - 1);
                addFlow(source, top);
                addFlow(top, target);
            }
        } else {
            flow.increaseTransitionCount();
            if (flow.isCall()) {
                callStack.add(flow.getSource());
            } else if (flow.isReturn()) {
                callStack.remove(callStack.size() - 1);
            }
        }
    }

    public Collection<Flow> getFlows() {
        return flows.values();
    }

    public Collection<FunctionCall> getFunctionCalls() {
        return functionCalls.values();
    }
}
