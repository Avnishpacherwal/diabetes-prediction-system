import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn import svm
import pickle

data=pd.read_csv('diabetes.csv')

X=data.drop(columns='Outcome',axis=1)
Y=data['Outcome']

scaler=StandardScaler()
X= scaler.fit_transform(X)

X_train, X_test, Y_train, Y_test = train_test_split(X,Y, test_size=0.2, stratify=Y, random_state=2)

model = svm.SVC(kernel='linear' , probability=True)

model.fit(X_train, Y_train)

#save the model
pickle.dump(model, open('model.pkl', 'wb'))
pickle.dump(scaler, open('scaler.pkl', 'wb'))

print("Model trained and saved successfully.")



















