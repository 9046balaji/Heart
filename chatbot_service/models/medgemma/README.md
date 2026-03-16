# MedGemma Model

## Why we use this model
MedGemma (specifically the quantized MedGemma-4B-IT model) serves as the core Large Language Model (LLM) for our medical chatbot service. We use MedGemma because it is formally fine-tuned for the medical domain, allowing it to thoroughly understand complex healthcare terminology, correctly interpret the RAG context, and provide safe, reliable medical answers. By running a quantized version locally, we ensure complete user privacy and maintain low-latency responses without relying on external cloud APIs to process sensitive health data.
