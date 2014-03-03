package br.uff.ic.sel.noworkflow.controller;

import br.uff.ic.sel.noworkflow.view.GraphFrame;
import java.io.File;
import java.util.logging.Level;
import java.util.logging.Logger;

public class NoWorkflow {

    public static void main(String[] args) {
                
        if (args.length != 2) {
            System.out.println("Please, inform the script path and the trial id.");
            System.out.println("Example: java -jar target/noWorkflowVis-0.1-jar-with-dependencies.jar ../tests/weather 1");
            System.exit(1);
        }

        File file = new File(args[0] + File.separator + ".noworkflow/db.sqlite");
        if (!file.exists()) {
            System.out.println("Could not find a noWorkflow repository at " + args[0]);
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
            final SQLiteReader reader = new SQLiteReader(file.getCanonicalPath(), trialId);
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
