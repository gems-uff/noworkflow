/* Precision, recall and F1 of a predictions file (columns Class,Pred). */
#include <stdio.h>

int main(int argc, char **argv) {
    if (argc != 3) return 2;
    FILE *in = fopen(argv[1], "r");
    if (!in) return 1;
    char header[256];
    long tp = 0, fp = 0, fn = 0, tn = 0;
    int truth, pred;
    fgets(header, sizeof header, in);
    while (fscanf(in, "%d,%d", &truth, &pred) == 2) {
        if (truth && pred) tp++;
        else if (!truth && pred) fp++;
        else if (truth && !pred) fn++;
        else tn++;
    }
    fclose(in);
    double precision = tp + fp ? (double) tp / (tp + fp) : 0.0;
    double recall = tp + fn ? (double) tp / (tp + fn) : 0.0;
    double f1 = precision + recall ? 2 * precision * recall / (precision + recall) : 0.0;
    FILE *out = fopen(argv[2], "w");
    if (!out) return 1;
    fprintf(out, "precision=%.4f\nrecall=%.4f\nF1=%.4f\n", precision, recall, f1);
    fclose(out);
    return 0;
}
