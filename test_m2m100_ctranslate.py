import ctranslate2
import sentencepiece as spm
from transformers import M2M100Tokenizer
import torch

# Load tokenizer
tokenizer = M2M100Tokenizer.from_pretrained("facebook/m2m100_418M")

# Load CTranslate2 translator
translator = ctranslate2.Translator("m2m100_ct2", device="cpu")  # or "cuda" for GPU

# Load SentencePiece model
sp = spm.SentencePieceProcessor()
sp.Load("m2m100_ct2/sentencepiece.bpe.model")  # Adjust path as needed

# Source sentence & languages
source_text = """
町の銭湯の廃業が止まらない。カフェや居酒屋に生まれ変わる銭湯もある中、入浴するという本来の機能を生かし、福祉の分野で活用しようと取り組む団体が出てきた。
朝9時、壁いっぱいに描かれた赤富士の下で、洗い場に座ったお年寄りがテレビを見ながら談笑していた。隣の男湯では、80代の男性が職員に身体を洗われ、湯船につかっている。「気持ち良くて嫌なことも忘れられるね」
長野県松本市の松本城近くにある「ばらの湯」。施設の老朽化に伴い、2021年に廃業した。66年の歴史があり、市内でも敷地面積が広く、地元客に愛された銭湯だった。"""
source_lang = "ja"
target_lang = "vi"

# Set language tokens
tokenizer.src_lang = source_lang
input_tokens = tokenizer.tokenize(source_text)
input_ids = tokenizer.convert_tokens_to_ids([f"__{source_lang}__"] + input_tokens)

# Convert to string tokens for CTranslate2
tokens = tokenizer.convert_ids_to_tokens(input_ids)

# Run translation
results = translator.translate_batch([tokens], target_prefix=[[f"__{target_lang}__"]])
output_tokens = results[0].hypotheses[0]

# Detokenize output
output_ids = tokenizer.convert_tokens_to_ids(output_tokens)
translated_text = tokenizer.decode(output_ids, skip_special_tokens=True)

print("Translated:", translated_text)
