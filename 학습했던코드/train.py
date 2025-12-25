from unsloth import FastLanguageModel
import torch
from trl import SFTTrainer
from transformers import TrainingArguments
from datasets import load_dataset
from unsloth.chat_templates import get_chat_template

# --- 1. 설정 ---
DATA_PATH = "/opt/dlami/nvme/data/qwen_0.5b_essential_data.jsonl"
OUTPUT_DIR = "/opt/dlami/nvme/outputs"
FINAL_SAVE_PATH = "/opt/dlami/nvme/qwen_finetuned"

max_seq_length = 2048
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name = "unsloth/Qwen2.5-0.5B-Instruct",
    max_seq_length = max_seq_length,
    dtype = None,
    load_in_4bit = True,
)

model = FastLanguageModel.get_peft_model(
    model,
    r = 16,
    target_modules = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    lora_alpha = 16,
    lora_dropout = 0, 
    bias = "none", 
    use_gradient_checkpointing = "unsloth", 
    random_state = 3407,
)

# --- 2. 데이터 로드 및 전처리 ---
# 데이터 로드
dataset = load_dataset("json", data_files=DATA_PATH, split="train")

# 템플릿 설정
tokenizer = get_chat_template(
    tokenizer,
    chat_template = "qwen-2.5",
    mapping = {"role" : "from", "content" : "value", "user" : "human", "assistant" : "gpt"},
)

def formatting_prompts_func(examples):
    convos = examples["messages"]
    texts = [tokenizer.apply_chat_template(convo, tokenize = False, add_generation_prompt = False) for convo in convos]
    return { "text" : texts, }

# 전체 데이터셋에 포맷팅 먼저 적용
dataset = dataset.map(formatting_prompts_func, batched = True)

# [핵심 변경] 학습/검증 데이터 분리 (9:1 비율)
# seed를 고정하여 매번 같은 데이터가 검증셋이 되도록 함
dataset_split = dataset.train_test_split(test_size=0.1, seed=3407)
train_dataset = dataset_split["train"]
eval_dataset = dataset_split["test"]

print(f"학습 데이터 개수: {len(train_dataset)}")
print(f"검증 데이터 개수: {len(eval_dataset)}")

# --- 3. 학습 설정 (고도화) ---
trainer = SFTTrainer(
    model = model,
    tokenizer = tokenizer,
    train_dataset = train_dataset, 
    eval_dataset = eval_dataset,   # 검증 데이터 추가
    dataset_text_field = "text",
    max_seq_length = max_seq_length,
    dataset_num_proc = 2,
    packing = True, 
    
args = TrainingArguments(
        # 배치 사이즈 유지
        per_device_train_batch_size = 4, 
        per_device_eval_batch_size = 4,
        
        # [핵심 1] 누적 스텝 1로 변경 (업데이트를 매번 수행 -> 학습 횟수 4배 증가 효과)
        gradient_accumulation_steps = 1, 
        
        # [핵심 2] 에폭을 15회로 대폭 증가 (데이터가 적으므로 반복 학습 필수)
        num_train_epochs = 15, 
        
        # [핵심 3] 워밍업 짧게
        warmup_steps = 10,
        
        # 학습률 유지
        learning_rate = 2e-4,
        fp16 = not torch.cuda.is_bf16_supported(),
        bf16 = torch.cuda.is_bf16_supported(),
        
        # [핵심 4] 로그를 5 스텝마다 찍어서 Loss 떨어지는지 감시
        logging_steps = 5,
        
        # 검증 설정 (과적합 감시)
        eval_strategy = "steps", 
        eval_steps = 50, 
        
        save_strategy = "steps",
        save_steps = 50,
        save_total_limit = 2,
        
        # 가장 Loss가 낮았던 똑똑한 모델 저장
        load_best_model_at_end = True,
        metric_for_best_model = "eval_loss",
        greater_is_better = False,
        
        optim = "adamw_8bit",
        weight_decay = 0.01,
        lr_scheduler_type = "linear",
        seed = 3407,
        output_dir = OUTPUT_DIR,
    ),
)

print("🚀 학습 시작 (Train/Val Split + Best Model Loading)...")
trainer.train()

print("💾 최적의 모델(Best Model) 저장 중...")
# load_best_model_at_end=True 덕분에 현재 model은 이미 가장 성능 좋은 상태임
model.save_pretrained_merged(FINAL_SAVE_PATH, tokenizer, save_method = "merged_16bit")