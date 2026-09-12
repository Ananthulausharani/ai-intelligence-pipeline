"""
Deterministic seed data representing verified, real AI startups and their known products.
Used for deterministic Phase IV entity resolution and canonicalization.
"""

from typing import Any

# Seed catalog of ~50 real known AI startups
SEED_STARTUPS: list[dict[str, Any]] = [
    {
        "canonical_name": "OpenAI",
        "aliases": ["OpenAI, Inc.", "Open AI", "OpenAI Inc", "OpenAI LP", "OpenAI Global LLC"],
        "products": ["ChatGPT", "Codex", "DALL-E", "Sora", "Whisper", "GPT-4", "GPT-4o"],
    },
    {
        "canonical_name": "Anthropic",
        "aliases": ["Anthropic, PBC", "Anthropic AI", "Anthropic PBC"],
        "products": ["Claude", "Claude 2", "Claude 3", "Claude 3.5 Sonnet", "Claude Opus"],
    },
    {
        "canonical_name": "Cohere",
        "aliases": ["Cohere Inc.", "Cohere Inc", "Cohere AI"],
        "products": ["Command", "Command R+", "Embed", "Rerank"],
    },
    {
        "canonical_name": "Mistral AI",
        "aliases": ["Mistral", "Mistral AI SAS", "Mistral AI, Inc."],
        "products": ["Le Chat", "Mistral Large", "Mixtral 8x7B", "Codestral"],
    },
    {
        "canonical_name": "Hugging Face",
        "aliases": ["Hugging Face, Inc.", "Hugging Face Inc", "HuggingFace"],
        "products": ["Transformers", "Hugging Face Hub", "Diffusers", "Inference Endpoints"],
    },
    {
        "canonical_name": "Scale AI",
        "aliases": ["Scale AI, Inc.", "Scale AI Inc", "Scale", "Scale.com"],
        "products": ["Scale Data Engine", "Scale GenAI Platform", "Scale Donovan"],
    },
    {
        "canonical_name": "Stability AI",
        "aliases": ["Stability.ai", "Stability AI Ltd", "Stability AI Ltd.", "Stability AI Inc"],
        "products": ["Stable Diffusion", "Stable Video Diffusion", "Stable Audio"],
    },
    {
        "canonical_name": "Midjourney",
        "aliases": ["Midjourney, Inc.", "Midjourney Inc"],
        "products": ["Midjourney v6"],
    },
    {
        "canonical_name": "Perplexity AI",
        "aliases": ["Perplexity", "Perplexity, Inc.", "Perplexity Inc", "Perplexity.ai"],
        "products": ["Perplexity Pro", "Perplexity Search", "Perplexity Enterprise"],
    },
    {
        "canonical_name": "Runway",
        "aliases": ["Runway AI", "Runway ML", "Runway, Inc.", "Runway AI, Inc."],
        "products": ["Gen-1", "Gen-2", "Gen-3 Alpha"],
    },
    {
        "canonical_name": "ElevenLabs",
        "aliases": ["Eleven Labs", "ElevenLabs Inc.", "ElevenLabs Inc"],
        "products": ["VoiceLab", "Voice Isolator", "Reader App"],
    },
    {
        "canonical_name": "Character.ai",
        "aliases": ["Character AI", "Character Technologies, Inc.", "Character Technologies"],
        "products": ["Character.ai Chat", "c.ai"],
    },
    {
        "canonical_name": "Adept AI",
        "aliases": ["Adept", "Adept AI Labs", "Adept AI Labs, Inc."],
        "products": ["ACT-1", "Adept Experiments"],
    },
    {
        "canonical_name": "Inflection AI",
        "aliases": ["Inflection", "Inflection AI, Inc.", "Inflection AI Inc"],
        "products": ["Pi", "Inflection-2.5"],
    },
    {
        "canonical_name": "Databricks",
        "aliases": ["Databricks, Inc.", "Databricks Inc"],
        "products": ["Mosaic AI", "Dolly", "DBRX"],
    },
    {
        "canonical_name": "Jasper",
        "aliases": ["Jasper AI", "Jasper.ai", "Jasper, Inc."],
        "products": ["Jasper AI Writer", "Jasper Studio"],
    },
    {
        "canonical_name": "Writer",
        "aliases": ["Writer, Inc.", "Writer AI", "Writer Inc"],
        "products": ["Palmyra", "Knowledge Graph"],
    },
    {
        "canonical_name": "Synthesia",
        "aliases": ["Synthesia Ltd", "Synthesia Ltd.", "Synthesia AI"],
        "products": ["Synthesia Studio", "Synthesia Video"],
    },
    {
        "canonical_name": "Replit",
        "aliases": ["Replit, Inc.", "Replit Inc"],
        "products": ["Replit Agent", "Ghostwriter"],
    },
    {
        "canonical_name": "Cursor",
        "aliases": ["Anysphere", "Anysphere, Inc.", "Anysphere Inc"],
        "products": ["Cursor Editor"],
    },
    {
        "canonical_name": "Poolside",
        "aliases": ["Poolside AI", "Poolside AI SAS"],
        "products": ["Poolside Coding Assistant"],
    },
    {
        "canonical_name": "Glean",
        "aliases": ["Glean Technologies, Inc.", "Glean Technologies"],
        "products": ["Glean Workplace Search", "Glean Assistant"],
    },
    {
        "canonical_name": "Harvey",
        "aliases": ["Harvey AI", "Harvey Technologies, Inc.", "Harvey Technologies"],
        "products": ["Harvey Legal AI"],
    },
    {
        "canonical_name": "Pika",
        "aliases": ["Pika Labs", "Pika Labs, Inc.", "Pika Art"],
        "products": ["Pika 1.0", "Pika Video"],
    },
    {
        "canonical_name": "Cognition",
        "aliases": ["Cognition AI", "Cognition Labs, Inc.", "Cognition Labs"],
        "products": ["Devin", "Devin AI"],
    },
    {
        "canonical_name": "Pinecone",
        "aliases": ["Pinecone Systems, Inc.", "Pinecone Systems"],
        "products": ["Pinecone Vector Database", "Pinecone Serverless"],
    },
    {
        "canonical_name": "Weaviate",
        "aliases": ["Weaviate B.V.", "Weaviate BV"],
        "products": ["Weaviate Cloud", "Weaviate Vector Search"],
    },
    {
        "canonical_name": "Qdrant",
        "aliases": ["Qdrant Solutions GmbH", "Qdrant Solutions"],
        "products": ["Qdrant Cloud"],
    },
    {
        "canonical_name": "Chroma",
        "aliases": ["Chroma, Inc.", "Chroma Inc", "ChromaDB"],
        "products": ["Chroma Hosted"],
    },
    {
        "canonical_name": "LangChain",
        "aliases": ["LangChain, Inc.", "LangChain Inc"],
        "products": ["LangSmith", "LangServe", "LangGraph"],
    },
    {
        "canonical_name": "LlamaIndex",
        "aliases": ["LlamaIndex Inc.", "LlamaIndex, Inc."],
        "products": ["LlamaCloud", "LlamaParse"],
    },
    {
        "canonical_name": "Weights & Biases",
        "aliases": ["W&B", "Weights and Biases, Inc.", "Weights & Biases, Inc."],
        "products": ["W&B Models", "W&B Weave"],
    },
    {
        "canonical_name": "Together AI",
        "aliases": ["Together.ai", "Together Computer, Inc.", "Together Computer"],
        "products": ["Together Inference Engine", "Together Cloud"],
    },
    {
        "canonical_name": "Anyscale",
        "aliases": ["Anyscale, Inc.", "Anyscale Inc"],
        "products": ["Ray", "Anyscale Endpoints"],
    },
    {
        "canonical_name": "Deepgram",
        "aliases": ["Deepgram, Inc.", "Deepgram Inc"],
        "products": ["Nova-2", "Deepgram Voice AI"],
    },
    {
        "canonical_name": "AssemblyAI",
        "aliases": ["AssemblyAI, Inc.", "AssemblyAI Inc"],
        "products": ["Conformer-2", "AssemblyAI Speech"],
    },
    {
        "canonical_name": "HeyGen",
        "aliases": ["HeyGen AI", "Movio", "Surreal, Inc."],
        "products": ["HeyGen Interactive Avatar"],
    },
    {
        "canonical_name": "Krea AI",
        "aliases": ["Krea", "Krea.ai", "Krea AI, Inc."],
        "products": ["Krea Realtime", "Krea Video"],
    },
    {
        "canonical_name": "Groq",
        "aliases": ["Groq, Inc.", "Groq Inc"],
        "products": ["Groq LPU", "GroqCloud"],
    },
    {
        "canonical_name": "Cerebras",
        "aliases": ["Cerebras Systems", "Cerebras Systems, Inc.", "Cerebras Systems Inc"],
        "products": ["CS-3", "Cerebras Inference"],
    },
    {
        "canonical_name": "Lambda",
        "aliases": ["Lambda Labs", "Lambda, Inc.", "Lambda Labs, Inc."],
        "products": ["Lambda Cloud", "Lambda Stack"],
    },
    {
        "canonical_name": "CoreWeave",
        "aliases": ["CoreWeave, Inc.", "CoreWeave Inc"],
        "products": ["CoreWeave Cloud"],
    },
    {
        "canonical_name": "Crusoe",
        "aliases": ["Crusoe Energy Systems", "Crusoe Cloud", "Crusoe Energy"],
        "products": ["Crusoe Cloud GPU"],
    },
    {
        "canonical_name": "Baseten",
        "aliases": ["Baseten, Inc.", "Baseten Inc"],
        "products": ["Truss", "Baseten Model Serving"],
    },
    {
        "canonical_name": "Modal",
        "aliases": ["Modal Labs", "Modal Labs, Inc.", "Modal Labs Inc"],
        "products": ["Modal Serverless"],
    },
    {
        "canonical_name": "Replicate",
        "aliases": ["Replicate, Inc.", "Replicate Inc"],
        "products": ["Cog", "Replicate Model API"],
    },
    {
        "canonical_name": "Fireworks AI",
        "aliases": ["Fireworks.ai", "Fireworks AI, Inc."],
        "products": ["Fireworks FireAttention", "Fireworks GenAI Platform"],
    },
    {
        "canonical_name": "Decagon",
        "aliases": ["Decagon AI", "Decagon, Inc.", "Decagon Inc"],
        "products": ["Decagon Customer Support AI"],
    },
    {
        "canonical_name": "Sierra",
        "aliases": ["Sierra AI", "Sierra Technologies, Inc.", "Sierra Technologies"],
        "products": ["Sierra Conversational Agent"],
    },
    {
        "canonical_name": "Mecka AI",
        "aliases": ["Mecka", "Mecka.ai", "Mecka AI, Inc."],
        "products": ["Mecka Robotics Engine", "Mecka Humanoid Data"],
    },
    {
        "canonical_name": "Method Financial",
        "aliases": ["Method Financial, Inc.", "Method Financial Inc", "Method"],
        "products": ["Method API", "Method Payments"],
    },
    {
        "canonical_name": "Replo",
        "aliases": ["Replo, Inc.", "Replo Inc"],
        "products": ["Replo Editor", "Replo AI"],
    },
]
