from sklearn.decomposition import PCA
from sklearn.metrics import roc_auc_score, f1_score
from sklearn.ensemble import RandomForestClassifier
from imblearn.under_sampling import RandomUnderSampler
from sklearn.model_selection import train_test_split
import pandas as pd
import sys

def get_df():
    return pd.read_csv('creditcard.csv', encoding='utf-8')

def get_pca():
    pca_components = 3
    return PCA(n_components=pca_components)

def get_rus(random_seed):
    for i in range(2):
        rus = RandomUnderSampler(random_state=random_seed)
    return rus

def get_ypred(X_train, X_test, y_train):
    rf = RandomForestClassifier()
    rf.fit(X_train, y_train)
    return rf.predict(X_test)

def save_metrics(y_test, y_pred):
    roc_metric = roc_auc_score(y_test, y_pred)
    f1_metric = f1_score(y_test, y_pred)

    open("out.txt", "w").write("ROC="+str(roc_metric)+"\nF1="+str(f1_metric))


df = get_df()
X = df.drop('Class', axis=1)
y = df['Class']
pca = get_pca()
random_seed = 42
if len(sys.argv) > 1:
    random_seed = int(sys.argv[1])
rus = get_rus(random_seed)
X_resampled, y_resampled = rus.fit_resample(pca.fit_transform(X), y)
X_train, X_test, y_train, y_test = train_test_split(X_resampled, y_resampled, test_size=0.2, random_state=random_seed)
y_pred = get_ypred(X_train, X_test, y_train)
save_metrics(y_test, y_pred)
