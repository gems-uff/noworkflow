# Logistic regression on the prepared dataset; writes the predictions.
args <- commandArgs(trailingOnly = TRUE)
input <- if (length(args) >= 1) args[1] else "prepared.csv"
output <- if (length(args) >= 2) args[2] else "pred.csv"
data <- read.csv(input)
set.seed(42)
test <- sample(nrow(data), floor(0.2 * nrow(data)))
model <- glm(Class ~ ., data = data[-test, ], family = binomial)
prob <- predict(model, newdata = data[test, ], type = "response")
threshold <- 0.5
write.csv(data.frame(Class = data$Class[test], Pred = as.integer(prob > threshold)),
          output, row.names = FALSE)
