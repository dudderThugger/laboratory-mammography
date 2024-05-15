import os

os.environ["CUDA_VISIBLE_DEVICES"] = "0,1,2"  # Choose which GPUs by checking current use with nvidia-smi
import tensorflow as tf
# import tensorflow_addons as tfa
from tensorflow import keras
## Keras library also provides ResNet101V2 and ResNet50V2. Import them and use it for other experiments.
from tensorflow.keras.applications import ResNet152V2
from tensorflow.keras.applications import ResNet50V2
from tensorflow.keras.callbacks import ReduceLROnPlateau, EarlyStopping
from tensorflow.keras.callbacks import ModelCheckpoint
from tensorflow.keras import metrics
import time
import numpy as np
from keras import backend as K

# Check CUDA functionality, restart kernel to change GPUs
gpus = tf.config.list_physical_devices('GPU')
print("*************************************")
print(gpus)
print("*************************************")


# Define function to preprocess images as required by ResNet
def preprocess(images, labels):
    return tf.keras.applications.resnet_v2.preprocess_input(images), labels


# setup train, validation, and test folders
traindir = '/mnt/d/datasets/INBREAST/split/train'
valdir = '/mnt/d/datasets/INBREAST/split/validation'
testdir = '/mnt/d/datasets/INBREAST/split/test'
dirName = '2_classes'

buffersize = 2
# im_dim = 512
im_dim_x = 224
im_dim_y = 224
batchSizeIntInitial = 10
batchSizeInt = 6

train = tf.keras.preprocessing.image_dataset_from_directory(
    traindir, image_size=(im_dim_x, im_dim_y), batch_size=batchSizeInt)
val = tf.keras.preprocessing.image_dataset_from_directory(
    valdir, image_size=(im_dim_x, im_dim_y), batch_size=batchSizeInt)
test = tf.keras.preprocessing.image_dataset_from_directory(
    testdir, image_size=(im_dim_x, im_dim_y), batch_size=batchSizeInt)

test_ds = test.map(preprocess)
train_ds = train.map(preprocess)
val_ds = val.map(preprocess)
train_ds = train_ds.prefetch(buffer_size=buffersize)
val_ds = val_ds.prefetch(buffer_size=buffersize)

## set up hyperparameters, such as epochs, learning rates, cutoffs.
epochs = 100
lr = 0.004
cutoff = 0.5
start_time = time.time()
mirrored_strategy = tf.distribute.MirroredStrategy()

with mirrored_strategy.scope():  # the entire model needs to be compiled within the scope of the distribution strategy
    # cb1 = EarlyStopping(monitor='val_accuracy', patience=4)  # define early stopping callback function
    cb1 = ModelCheckpoint("/mnt/d/datasets/INBREAST/results/resnet50.h5", monitor="val_accuracy", verbose=2, save_best_only=True, mode="max")
    # cb2 = ReduceLROnPlateau(monitor='val_accuracy', factor=0.2, patience=2,
    #                         min_lr=0.00001)  # define LR reduction callback function
    opt = keras.optimizers.Adam(learning_rate=lr)
    metr = [metrics.BinaryAccuracy(name='accuracy', threshold=cutoff), metrics.AUC(name='auc'),
            metrics.Precision(name='precision'),
            metrics.Recall(name='recall')]
    #                 tfa.metrics.F1Score(name='f1_score')]
    ptmodel = ResNet50V2(include_top=False, weights='imagenet', classes=2, input_shape=(im_dim_x, im_dim_y, 3),
                         pooling='avg')  # compile resnet152v2 with imagenet weights
    ptmodel.trainable = False  # freeze layers
    ptmodel.layers[-1].trainable = True


    # un-freeze the BatchNorm layers
    # for layer in ptmodel.layers:
    #     if "BatchNormalization" in layer.__class__.__name__:
    #         layer.trainable = False # ??

    last_output = ptmodel.output
    x = tf.keras.layers.Flatten()(last_output)
    # x = tf.keras.layers.Dense(2048, activation='relu')(x)
    # #     x = tf.keras.layers.Dropout(0.15)(x)
    # x = tf.keras.layers.Dense(1024, activation='relu')(x)
    # #    x = tf.keras.layers.Dropout(0.3)(x)
    x = tf.keras.layers.Dense(512, activation='relu')(x)
    x = tf.keras.layers.Dense(128, activation='relu')(x)
    x = tf.keras.layers.Dense(32, activation='relu')(x)
    # # x = tf.keras.layers.Dropout(0.5, seed=34)(x)
    # x = tf.keras.layers.Dense(64, activation = 'relu')(x)
    x = tf.keras.layers.Dense(1, activation='sigmoid')(x)
    model = tf.keras.Model(ptmodel.input, x)
    model.compile(optimizer=opt,
                  loss='BinaryCrossentropy',
                  metrics=metr)

print("---time taken : %s seconds ---" % (time.time() - start_time))
# Train model
history = model.fit(train_ds, validation_data=val_ds, epochs=epochs, callbacks=[cb1])
print("---time taken : %s seconds ---" % (time.time() - start_time))
# Test model
# Loading checkpoint model
model.load_weights("resnet50.h5")
testloss, testaccuracy, testauc, precision, recall = model.evaluate(test_ds)
print('Test accuracy :', testaccuracy)
print('Test AUC :', testauc)

F1 = 2 * float(precision) * float(recall) / (float(precision) + float(recall))
print('Test F1 :', F1)
print('Test precision :', precision)
print('Test recall :', recall)

# Model path setup.
if not os.path.exists("saved_model_resnet50_simple" + dirName):
    os.makedirs("saved_model_resnet50_simple" + dirName + '/')

model.save('saved_model_resnet50_simple' + dirName + '/resnet152v2_1')
predicted_probs = np.array([])
true_classes = np.array([])
IterationChecker = 0
for images, labels in test_ds:
    if IterationChecker == 0:
        predicted_probs = model(images)
        true_classes = labels.numpy()

    IterationChecker += 1

    predicted_probs = np.concatenate([predicted_probs,
                                      model(images)])
    true_classes = np.concatenate([true_classes, labels.numpy()])
# Since they are sigmoid outputs, you need to transform them into classes with a threshold, i.e 0.5 here:
predicted_classes = [1 * (x[0] >= cutoff) for x in predicted_probs]
# confusion matrix etc:
conf_matrix = tf.math.confusion_matrix(true_classes, predicted_classes)
print(conf_matrix)

predicted_probs = np.squeeze(predicted_probs)
predicted_classes = np.array(predicted_classes)
true_classes = np.squeeze(true_classes)
summedResults = np.stack((predicted_probs, predicted_classes, true_classes), axis=1)
##Print out statistics which test files are correctly predicted or not.
np.savetxt("Resnet50_simple_comp_EMBED.csv", summedResults, delimiter=',',
           header="predicted_probabilty,predicted_classes,true_classes", comments="")