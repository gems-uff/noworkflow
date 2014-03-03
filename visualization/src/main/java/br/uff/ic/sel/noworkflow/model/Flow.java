package br.uff.ic.sel.noworkflow.model;

public class Flow {
    public enum Type { SEQUENCE, CALL, RETURN }

    private Type type;
    private FunctionCall source;
    private FunctionCall target;
    private int transitionCount = 1;

    public Flow(FunctionCall source, FunctionCall target, Type type) {
        this.source = source;
        this.target = target;
        this.type = type;
    }

    public FunctionCall getSource() {
        return source;
    }

    public FunctionCall getTarget() {
        return target;
    }
    
    public void increaseTransitionCount() {
        transitionCount++;
    }
    
    public int getTransitionCount() {
        return transitionCount;
    }
    
    public boolean isSequence() {
        return type == Type.SEQUENCE;
    }

    public boolean isCall() {
        return type == Type.CALL;
    }
    
    public boolean isReturn() {
        return type == Type.RETURN;
    }

    @Override
    public String toString() {
        return source.getName() + " -- " + type + " (" + transitionCount + ") --> " + target.getName();
    }
}