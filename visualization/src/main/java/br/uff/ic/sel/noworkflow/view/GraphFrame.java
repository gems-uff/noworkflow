package br.uff.ic.sel.noworkflow.view;

import br.uff.ic.sel.noworkflow.model.Flow;
import br.uff.ic.sel.noworkflow.model.FunctionCall;
import edu.uci.ics.jung.algorithms.layout.Layout;
import edu.uci.ics.jung.algorithms.layout.SpringLayout2;
import edu.uci.ics.jung.graph.DirectedGraph;
import edu.uci.ics.jung.graph.DirectedSparseGraph;
import edu.uci.ics.jung.visualization.VisualizationViewer;
import edu.uci.ics.jung.visualization.control.DefaultModalGraphMouse;
import java.awt.BorderLayout;
import java.awt.Color;
import java.awt.Paint;
import java.util.Collection;
import org.apache.commons.collections15.Transformer;

public class GraphFrame extends javax.swing.JFrame {

    /**
     * Creates new form GraphFrame
     */
    public GraphFrame(Collection<FunctionCall> functionCalls, Collection<Flow> flows) {
        setDefaultCloseOperation(javax.swing.WindowConstants.EXIT_ON_CLOSE);
        setTitle("noWorkflow Graph Visualizer");
        setSize(800, 600);
        setLocationRelativeTo(null);

        DirectedGraph<FunctionCall, Flow> graph = getGraph(functionCalls, flows);
        VisualizationViewer<FunctionCall, Flow> viewer = getViewer(graph);

        getContentPane().setLayout(new BorderLayout());
        getContentPane().add(viewer, BorderLayout.CENTER);
    }

    private DirectedGraph<FunctionCall, Flow> getGraph(Collection<FunctionCall> functionCalls, Collection<Flow> flows) {
        DirectedGraph<FunctionCall, Flow> graph = new DirectedSparseGraph<>();
        for (FunctionCall functionCall : functionCalls) {
            graph.addVertex(functionCall);
        }
        for (Flow flow : flows) {
            graph.addEdge(flow, flow.getSource(), flow.getTarget());
        }
        return graph;
    }

    private VisualizationViewer<FunctionCall, Flow> getViewer(DirectedGraph<FunctionCall, Flow> graph) {
        // Choosing layout
//        Layout<Researcher, Indication> layout = new CircleLayout<Researcher, Indication>(graph);
//        Layout<Researcher, Indication> layout = new FRLayout2<Researcher, Indication>(graph);
//        Layout<Researcher, Indication> layout = new ISOMLayout<Researcher, Indication>(graph);
//        Layout<Researcher, Indication> layout = new KKLayout<>(graph);
        Layout<FunctionCall, Flow> layout = new SpringLayout2<>(graph);
        VisualizationViewer<FunctionCall, Flow> viewer = new VisualizationViewer<>(layout);

        // Adding interation via mouse
        DefaultModalGraphMouse mouse = new DefaultModalGraphMouse();
        viewer.setGraphMouse(mouse);
        viewer.addKeyListener(mouse.getModeKeyListener());

        // Labelling vertices
        //view.getRenderContext().setVertexLabelTransformer(new ToStringLabeller<FunctionCall>());
        Transformer vertexLabeller = new Transformer<FunctionCall, String>() {
            public String transform(FunctionCall functionCall) {
                return functionCall.getName();
            }
        };
        viewer.getRenderContext().setVertexLabelTransformer(vertexLabeller);

        // Labelling edges
        //view.getRenderContext().setVertexLabelTransformer(new ToStringLabeller<FunctionCall>());
        Transformer edgeLabeller = new Transformer<Flow, String>() {
            public String transform(Flow flow) {
                return Integer.toString(flow.getTransitionCount());
            }
        };
        viewer.getRenderContext().setEdgeLabelTransformer(edgeLabeller);

        // Painting vertices
        Transformer vertexPainter = new Transformer<FunctionCall, Paint>() {
            @Override
            public Paint transform(FunctionCall functionCall) {
                int tone = Math.round(250);  // * ( 1 - researcher.getNominationsCount() / (float) Function.getMaxNominationsCount() ));
                //return new Color(tone, tone, tone);
                return new Color(72, 61, 139);
            }
        };
        viewer.getRenderContext().setVertexFillPaintTransformer(vertexPainter);
        viewer.getRenderContext().setVertexDrawPaintTransformer(vertexPainter);

        // Painting edges
        Transformer edgePainter = new Transformer<Flow, Paint>() {
            @Override
            public Paint transform(Flow indication) {
                int tone = Math.round(0); // * ( 1 - indication.getSource().getNominationsCount() / (float) Function.getMaxNominationsCount() ));
                return new Color(tone, tone, tone);
            }
        };
        viewer.getRenderContext().setEdgeDrawPaintTransformer(edgePainter);
        viewer.getRenderContext().setArrowDrawPaintTransformer(edgePainter);
        viewer.getRenderContext().setArrowFillPaintTransformer(edgePainter);

        viewer.setBackground(Color.white);

        return viewer;
    }
}