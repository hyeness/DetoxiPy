import pandas as pd
import numpy as np
from keras.preprocessing import text, sequence
from dataprep.data_prep import TextPrep
from featurecreation.embeddings_loader import EmbeddingsLoader
from modelling.nn_models import LSTMModels
from sklearn.model_selection import train_test_split
import torch
from torch import nn
from torch.utils import data
from torch.nn import functional as F
import os
import time
import gc
import random


def seed_everything(seed=1234): 
    """
    Sets a random seed for every randomly generated variables 
    in the pipeline.

    Input: Int

    """
    random.seed(seed)
    os.environ['PYTHONHASHSEED'] = str(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed(seed)
    torch.backends.cudnn.deterministic = True


def build_datasets(train_path, data_sample_frac, text_colname, text_prepper,  
                   cln_rmCaps, cln_mapPunct, cln_clSpecial, cln_spChk, 
                   cln_replaceId, cln_rmStop, cln_stem, cln_mpContract, 
                   target_colname, aux_target_colnames, tokenizer, 
                   txt_token_seq_len, test_frac = 0.3):
    """
     i) Loads a dataframe froma given path, splits it into train and test sets
     ii) Cleans, tokenizes, and sequences its text features column.

    """

    df = pd.read_csv(train_path).sample(frac = data_sample_frac)
    
    # DIVIDING INTO TRAINING AND TESTING
    train, test = train_test_split(df, test_size=test_frac)

    # SPLITTING INTO X AND Y COLUMNS, APPLYING PREPROCESSING
    x_train = train[text_colname]
    x_train = x_train.apply(text_prepper.clean, rmCaps = cln_rmCaps, 
                            mapPunct = cln_mapPunct, clSpecial = cln_clSpecial, 
                            spCheck = cln_spChk, replaceId = cln_replaceId, 
                            rmStop = cln_rmStop, stem = cln_stem, 
                            mpContract = cln_mpContract)
    y_train = np.where(train[target_colname] >= 0.5, 1, 0)
    y_aux_train = train[aux_target_colnames]
    
    x_test = test[text_colname]
    x_test = x_test.apply(text_prepper.clean, rmCaps = cln_rmCaps, 
                          mapPunct = cln_mapPunct, clSpecial = cln_clSpecial, 
                          spCheck = cln_spChk, replaceId = cln_replaceId, 
                          rmStop = cln_rmStop, stem = cln_stem, 
                          mpContract = cln_mpContract)

    # PROCESSING TEXT SEQUENCES    
    tokenizer.fit_on_texts(list(x_train) + list(x_test))
    x_train = tokenizer.texts_to_sequences(x_train)
    x_test = tokenizer.texts_to_sequences(x_test)
    x_train = sequence.pad_sequences(x_train, maxlen = txt_token_seq_len)
    x_test = sequence.pad_sequences(x_test, maxlen = txt_token_seq_len)
    print('DATASETS READY:')
    
    return x_train, x_test, y_train, y_aux_train, tokenizer, train, test

def build_model(x_train, y_train, x_test, y_aux_train, glove_matrix, num_models,
                model_type='LSTM'):

    """
    Instantiates a NN model, trains it over the train set,  and tests it over
    a given test set, returning the class probabilities for each unseen 
    observation.

    """
    
    x_train_torch = torch.tensor(x_train, dtype=torch.long)
    x_test_torch = torch.tensor(x_test, dtype=torch.long)
    y_train_torch = torch.tensor(np.hstack([y_train[:, np.newaxis], y_aux_train]),
                                 dtype=torch.float32)
    train_dataset = data.TensorDataset(x_train_torch, y_train_torch)
    test_dataset = data.TensorDataset(x_test_torch)

    all_test_preds = []

    for model_idx in range(num_models):
        print('Model ', model_idx)
        if model_type=='LSTM':
            model = LSTMModels(glove_matrix, y_aux_train.shape[-1]) 
        elif model_type=='GRU':
            model = NeuralNetGRU(glove_matrix, y_aux_train.shape[-1])
        else:
            print("Invalid model type")
            break

        test_preds = model.train_model(train_dataset, test_dataset,
                output_dim=y_train_torch.shape[-1], 
                                 loss_fn=nn.BCEWithLogitsLoss(reduction='mean'))
        all_test_preds.append(test_preds)
        print()
    return all_test_preds

# BIAS AND OVERALL PERFORMANCE

def get_overall_perf(test, res, thresh=0.5):
    """
    Computes overall performance metrics for a binary  classification
    model over a test set, given a class probability threshold.

    """
    accuracy, precision, recall = None, None, None
    test['probs'] = res['prediction']
    test['preds'] = test['probs'].apply(lambda x: 1 if x >= thresh else 0)
    test['true'] = test['target'].apply(lambda x: 1 if x >= thresh else 0)
    test['correct'] = test['true']==test['preds']
    test['correct'] = test['correct'].apply(lambda x: 1 if x == True else 0)
    test1prec = test[test['preds'] == 1]
    accuracy = test['correct'].sum()/len(test) 
    lenp = len(test1prec)
    if lenp > 0:
        precision = test1prec['correct'].sum()/lenp
    print("Overall Accuracy: {} \n Overall Precision: {}".format(accuracy,precision))
    return test, accuracy, precision

def get_performance(test, precision, ident_collist, thresh=0.5, wb=0.3, wp=0.7):
    """
    Partitions the dataset into identity-relatedd or not, computes model bias 
    defined as the difference between precision score in both sets of observations,
    and calculates model performace as a weighted average of 1-bias and 
    overall precision in the full dataset.

    """
    
    def wav(bias, prec, wb, wp):
        """
        Computes a weighted average of 1-bias and 
        overall precision in the full dataset
        """
        return wb*(1-bias) + (wp*prec)
    
    test['identity']=(test[ident_collist]>=0.5).max(axis=1).astype(bool)

    test['identity'] = test['identity'].apply(lambda x: 1 if x else 0)
        
    testID = test[test['identity'] == 1]
    testNONID = test[test['identity'] == 0]
    
    testIDprec = testID[testID['preds'] == 1]
    accuracyID = testID['correct'].sum()/len(testID) 
    lenpid = len(testIDprec)
    if lenpid > 0:
        precID = testIDprec ['correct'].sum()/lenpid 
    
    testNONIDprec = testNONID[testNONID['preds'] == 1]
    accuracyNONID = testNONID['correct'].sum()/len(testNONID) 
    lenpnonid = len(testNONIDprec)
    if lenpnonid  > 0:
        precNONID = testNONIDprec['correct'].sum()/lenpnonid

    bias = precNONID - precID
    perf = wav(bias, precision, wb, wp)
    print("Bias: {}, \n Overall Performance: {}".format(bias, perf))
    return test, perf, bias

# DATAREAD PARAMETERS
train_path = "train.csv"
data_sample_frac = 0.05
text_colname = "comment_text"
target_colname = "target"
aux_target_colnames = ["target", "severe_toxicity", "obscene", "identity_attack", "insult", "threat"]
train_data_sample = 0.3
test_frac = 0.3
IDENT_LIST = ['asian', 'atheist', 'bisexual', 'black', 'buddhist',  'christian', 'female', 'heterosexual',
'hindu', 'homosexual_gay_or_lesbian','intellectual_or_learning_disability','jewish','latino','male',
'muslim','other_disability','other_gender','other_race_or_ethnicity','other_religion', 'other_sexual_orientation',
              'physical_disability','psychiatric_or_mental_illness', 'transgender', 'white']

# DATAPROC PARAMETERS

text_prepper = TextPrep()
cln_rmCaps = True
cln_mapPunct = True
cln_clSpecial = True
cln_spChk = False 
cln_replaceId = False
cln_rmStop = False
cln_stem = False
cln_mpContract = True
tokenizer = text.Tokenizer()
txt_token_seq_len = 220

# EMBEDDINGS LOADER PARAMETERS

embed_type = "word2vec"
#wrd_to_ix_dict = tokenizer.word_index
#pretrained_embed_path = "featurecreation/embeddings/small_sample_vector_100K_ft.kv"
pretrained_embed_path = "featurecreation/embeddings/threequarters_sample_vector_noIDrepl_w2v.kv"


def main (cln_replaceId = False):
    """
    Main function: loads and process dataset, builds word embedding,
    trains and tests model, and computes model performance metrics, 
    using global parameters.

    """
    # SETTING SEED
    seed_everything()

    # BUILDING DATASET
    data_result_set = build_datasets(train_path, data_sample_frac, text_colname, 
                                    text_prepper, cln_rmCaps, cln_mapPunct, 
                                    cln_clSpecial, cln_spChk, cln_replaceId, 
                                    cln_rmStop, cln_stem, cln_mpContract, 
                                    target_colname, aux_target_colnames, tokenizer,
                                    txt_token_seq_len, test_frac)

    x_train = data_result_set[0]
    x_test = data_result_set[1]
    y_train = data_result_set[2]
    y_aux_train = data_result_set[3]
    tokenizer_trained = data_result_set[4]
    wrd_to_ix_dict = tokenizer_trained.word_index
    train = data_result_set[5]
    test = data_result_set[6]

    # LOADING EMBEDDINGS
    embed_loader = EmbeddingsLoader(embed_type = embed_type, 
                                    wrd_to_ix_dict = wrd_to_ix_dict,
                                    pretrained_embed_path = pretrained_embed_path)

    # MODEL EVALUATION
    emb_matrix = embed_loader.embeddings_matrix

    test_preds = build_model(x_train, y_train, x_test, y_aux_train, emb_matrix, num_models=1,
                    model_type='LSTM')

    res = pd.DataFrame.from_dict({ 'id': test['id'], 'prediction': np.mean(test_preds,
                axis=0)[:, 0]})
    test_expand, accuracy, precision = get_overall_perf(test, res)
        
    return get_performance(test_expand, precision, ident_collist=IDENT_LIST)
