import sys
sys.path.insert(0, '.')
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch

t = AutoTokenizer.from_pretrained('./model/distilbert_model', local_files_only=True)
m = AutoModelForSequenceClassification.from_pretrained('./model/distilbert_model', local_files_only=True)
m.eval()

inputs = t('Hello wolmfed thsi is Ptrean', return_tensors='pt')
with torch.no_grad():
    probs = m(**inputs).logits.softmax(dim=1)[0]

print('id2label :', m.config.id2label)
print('probs    :', probs)
print('argmax   :', probs.argmax().item(), '→', m.config.id2label[probs.argmax().item()])
