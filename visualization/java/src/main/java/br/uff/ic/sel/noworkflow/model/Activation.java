package br.uff.ic.sel.noworkflow.model;

import java.sql.Timestamp;
import java.util.Map;

public class Activation {
    private int id;
    private Map<String, String> arguments;
    private String returnValue;
    private Timestamp start;
    private Timestamp finish;

    public Activation(int id, Map<String, String> arguments, String returnValue, Timestamp start, Timestamp finish) {
        this.id = id;
        this.arguments = arguments;
        this.returnValue = returnValue;
        this.start = start;
        this.finish = finish;
    }

    public int getId() {
        return id;
    }

    public Map<String, String> getArguments() {
        return arguments;
    }

    public String getReturnValue() {
        return returnValue;
    }

    public Timestamp getStart() {
        return start;
    }

    public Timestamp getFinish() {
        return finish;
    }   
    
    /**
     * Informs the duration of an activation in nanoseconds
     */
    public long getDuration() {
        return 1000000 * (finish.getTime() - start.getTime()) + (finish.getNanos() % 1000000 - start.getNanos() % 1000000);
    }
    
    @Override
    public String toString() {
        StringBuilder text = new StringBuilder("  Activation " + id + " from " + start + " to " + finish);
        for (String arg : arguments.keySet()) {
            text.append("\n    ").append("Argument ").append(arg).append(" = ").append(arguments.get(arg));
        }
        text.append("\n    ").append("Return ").append(returnValue);
        return text.toString();
    }
    
    public String toHtml() {
        StringBuilder text = new StringBuilder("Activation #").append(id);
        text.append(" from ").append(start).append(" to ").append(finish).append(" (").append(getDuration()).append(" nanoseconds)");
        for (String arg : arguments.keySet()) {
            text.append("<br/>").append("Argument ").append(arg).append(" = ").append(arguments.get(arg));
        }
        text.append("<br/>").append("Returned ").append(returnValue);
        return text.toString();
    }
}
