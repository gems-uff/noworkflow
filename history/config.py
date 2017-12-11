from config_elements import Author, Blank, Paper

configuration = {
    (2013, 9, 5): [
        Author("leo.jpg", "Leonardo Murta", "leomurta@ic.uff.br"), 
        Author("vanessa.jpg", "Vanessa Braganholo", "vanessa@ic.uff.br"),
        Author("juliana.jpg", "Juliana Freire", "juliana.freire@nyu.edu"),
        Author("david.jpg", "David Koop", "dakoop@nyu.edu"),
        Author("fernando.jpg", "Fernando Chirigati", "fchirigati@nyu.edu"),
    ],
    (2014, 6, 1): [
        Paper("MURTA, L. G. P.; BRAGANHOLO, V.; CHIRIGATI, F. S.; KOOP, D.; FREIRE, J.; noWorkflow: Capturing and Analyzing Provenance of Scripts. In: International Provenance and Annotation Workshop (IPAW), 2014, Cologne, Germany.",
              "https://github.com/gems-uff/noworkflow/raw/master/docs/ipaw2014.pdf"),
    ],
    (2014, 7, 5): [
        Blank(),
        Author("joao.jpg", "Joao Felipe Pimentel", "jpimentel@ic.uff.br"), 
    ],
    (2015, 6, 1): [
        Paper("PIMENTEL, J. F. N.; FREIRE, J.; MURTA, L. G. P.; BRAGANHOLO, V.; Collecting and Analyzing Provenance on Interactive Notebooks: when IPython meets noWorkflow. In: Theory and Practice of Provenance (TaPP), 2015, Edinburgh, Scotland.",
              "https://github.com/gems-uff/noworkflow/raw/master/docs/tapp2015.pdf"),
    ],
    (2016, 6, 1): [
        Paper("PIMENTEL, J. F.; FREIRE, J.; BRAGANHOLO, V.; MURTA, L. G. P.; Tracking and Analyzing the Evolution of Provenance from Scripts. In: International Provenance and Annotation Workshop (IPAW), 2016, McLean, Virginia.",
              "https://github.com/gems-uff/noworkflow/raw/master/docs/ipaw2016a.pdf"),
        Paper("PIMENTEL, J. F.; FREIRE, J.; MURTA, L. G. P.; BRAGANHOLO, V.; Fine-grained Provenance Collection over Scripts Through Program Slicing. In: International Provenance and Annotation Workshop (IPAW), 2016, McLean, Virginia.",
              "https://github.com/gems-uff/noworkflow/raw/master/docs/ipaw2016b.pdf"),
        Paper("PIMENTEL, J. F.; DEY, S.; MCPHILLIPS, T.; BELHAJJAME, K.; KOOP, D.; MURTA, L. G. P.; BRAGANHOLO, V.; LUDÄSCHER B.; Yin & Yang: Demonstrating Complementary Provenance from noWorkflow & YesWorkflow. In: International Provenance and Annotation Workshop (IPAW), 2016, McLean, Virginia.",
              "https://github.com/gems-uff/noworkflow/raw/master/docs/ipaw2016c.pdf"),
    ],
    (2017, 8, 1): [
        Paper("PIMENTEL, J. F.; MURTA, L. G. P.; BRAGANHOLO, V.; FREIRE, J.; noWorkflow: a Tool for Collecting, Analyzing, and Managing Provenance from Python Scripts. In: International Conference on Very Large Data Bases (VLDB), 2017, Munich, Germany.",
              "https://github.com/gems-uff/noworkflow/raw/master/docs/vldb2017.pdf"),
    ],
}