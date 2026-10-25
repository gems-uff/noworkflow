# The model.R of the case study with its threshold sourced from utils.R:
# a file the R script reads that is named on no command line, which only a
# tracer of the child's system calls can see (the strace variant of the
# "Beyond Python" tests).
args <- commandArgs(trailingOnly = TRUE)
input <- if (length(args) >= 1) args[1] else "prepared.csv"
output <- if (length(args) >= 2) args[2] else "pred.csv"
data <- read.csv(input)
set.seed(42)
test <- sample(nrow(data), floor(0.2 * nrow(data)))
model <- glm(Class ~ ., data = data[-test, ], family = binomial)
prob <- predict(model, newdata = data[test, ], type = "response")
source("utils.R")
write.csv(data.frame(Class = data$Class[test], Pred = as.integer(prob > threshold)),
          output, row.names = FALSE)
