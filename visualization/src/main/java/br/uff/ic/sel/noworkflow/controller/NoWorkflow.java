package br.uff.ic.sel.noworkflow.controller;

import br.uff.ic.sel.noworkflow.model.Flow;
import br.uff.ic.sel.noworkflow.model.FunctionCall;
import br.uff.ic.sel.noworkflow.view.GraphFrame;
import edu.uci.ics.jung.graph.DirectedGraph;
import edu.uci.ics.jung.graph.DirectedSparseGraph;
import java.io.File;
import java.util.logging.Level;
import java.util.logging.Logger;

public class NoWorkflow {

    public static void main(String[] args) {
        if (args.length != 2) {
            System.out.println("Please, inform the database path and the trial id.");
            System.out.println("Example: java -jar target/noWorkflowVis-0.1-jar-with-dependencies.jar ../tests/weather/.noworkflow/db.sqlite 1");
            System.exit(1);
        }

        File file = new File(args[0]);
        if (!file.exists()) {
            System.out.println("Could not find a SQLite database at " + args[0]);
            System.exit(1);
        }
        
        int trialId = -1;
        try {
            trialId = Integer.parseInt(args[1]);
        } catch (Exception e) {
            System.out.println("The second argument is not a trial id");
            System.exit(1);            
        }
        
        try {
            final SQLiteReader reader = new SQLiteReader(args[0], trialId);

//        for (FunctionCall f : reader.getFunctionCalls()) {
//            System.out.println(f);
//        }
//        
//        for (Flow f : reader.getFlows()) {
//            System.out.println(f);
//        }

            java.awt.EventQueue.invokeLater(new Runnable() {
                public void run() {
                    new GraphFrame(reader.getFunctionCalls(), reader.getFlows()).setVisible(true);
                }
            });
        }
        catch (Exception ex) {
            Logger.getLogger(GraphFrame.class.getName()).log(Level.SEVERE, null, ex);
        }

    }
}
