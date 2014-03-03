package br.uff.ic.sel.noworkflow.model;

import java.sql.Timestamp;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

public class FunctionCall {

    private int callerId;
    private int line;
    private String name;
    private List<Activation> activations;

    public FunctionCall(int callerId, int line, String name, int id, Map<String, String> arguments, String returnValue, Timestamp start, Timestamp finish) {
        this.callerId = callerId;
        this.line = line;
        this.name = name;
        this.activations = new ArrayList<>();
        activations.add(new Activation(id, arguments, returnValue, start, finish));
    }

    public int getCallerId() {
        return callerId;
    }

    public int getLine() {
        return line;
    }

    public String getName() {
        return name;
    }
    
    /**
     * Informs the mean duration of all activation of this function call in milliseconds
     */
    public long getMeanDuration() {
        long sum = 0;
        for (Activation activation : activations) {
            sum += activation.getDuration();
        }
        return sum / activations.size();
        
    }

    public void addActivation(int id, Map<String, String> arguments, String returnValue, Timestamp start, Timestamp finish) {
        activations.add(new Activation(id, arguments, returnValue, start, finish));        
    }
    
    public boolean hasActivation(int id) {
        for (Activation a : activations) { // TODO: Use binary search
            if (id == a.getId()) {
                return true;
            }
        }
        return false;
    }
    
    @Override
    public String toString() {
        StringBuilder text = new StringBuilder("Function " + name + " called by " + callerId + " at line " + line);
        for (Activation activation : activations) {
            text.append("\n").append(activation);
        }
        return text.toString();
    }
}