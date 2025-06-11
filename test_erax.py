import time
import torch
from transformers import M2M100ForConditionalGeneration, M2M100Tokenizer

# Check if GPU is available
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Using device: {device}")

start = time.time()
print("Loading model and tokenizer...")
model = M2M100ForConditionalGeneration.from_pretrained("facebook/m2m100_418M").to(device)
tokenizer = M2M100Tokenizer.from_pretrained("facebook/m2m100_418M")
print(f"Model and tokenizer loaded in {time.time() - start:.2f} seconds.")

hi_text = """町の銭湯の廃業が止まらない。カフェや居酒屋に生まれ変わる銭湯もある中、入浴するという本来の機能を生かし、福祉の分野で活用しようと取り組む団体が出てきた。
朝9時、壁いっぱいに描かれた赤富士の下で、洗い場に座ったお年寄りがテレビを見ながら談笑していた。隣の男湯では、80代の男性が職員に身体を洗われ、湯船につかっている。「気持ち良くて嫌なことも忘れられるね」
長野県松本市の松本城近くにある「ばらの湯」。施設の老朽化に伴い、2021年に廃業した。66年の歴史があり、市内でも敷地面積が広く、地元客に愛された銭湯だった。"""

tokenizer.src_lang = "ja"

# Split into sentences
hi_text = hi_text.replace("。", "。\n").replace("！", "！\n").replace("？", "？\n").strip()
hi_text = [s.strip() for s in hi_text.split("\n") if s.strip()]
print(f"Number of sentences to translate: {len(hi_text)}")

# Translate each sentence
for i, sentence in enumerate(hi_text):
    start = time.time()
    encoded = tokenizer(sentence, return_tensors="pt").to(device)  # ← move to GPU
    generated_tokens = model.generate(
        **encoded, forced_bos_token_id=tokenizer.get_lang_id("vi")
    )
    trans = tokenizer.batch_decode(generated_tokens, skip_special_tokens=True)
    print(f"\nTranslation {i + 1}/{len(hi_text)}:")
    print(trans[0])
    print(f"Translation took {time.time() - start:.2f} seconds.")