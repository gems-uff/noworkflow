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
     * Informs the total duration of all activation of this function call in
     * nanoseconds
     */
    public long getTotalDuration() {
        long sum = 0;
        for (Activation activation : activations) {
            sum += activation.getDuration();
        }
        return sum;
    }
    
    /**
     * Informs the mean duration of all activation of this function call in
     * nanoseconds
     */
    public long getMeanDuration() {
        return getTotalDuration() / activations.size();
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

    public String toHtml() {
        long totalDuration = getTotalDuration();
        StringBuilder text = new StringBuilder();
        text.append("<html>");
        text.append("Function <b>").append(name).append("</b> called at line ").append(line);
        text.append("<br/>Total duration of ").append(totalDuration).append(" nanoseconds for ").append(activations.size()).append(" activations (mean of ").append(totalDuration / activations.size()).append(" nanoseconds per activation)");

        for (Activation activation : activations) {
            text.append("<br/><br/>");
            text.append(activation.toHtml());
        }
        text.append("</html>");
        return text.toString();
    }
}