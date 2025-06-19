# check_torch.py
import torch

try:
    is_available = torch.cuda.is_available()
    print(f"PyTorch Version: {torch.__version__}")
    print(f"CUDA is available: {is_available}")

    if is_available:
        print(f"Device count: {torch.cuda.device_count()}")
        print(f"Current device: {torch.cuda.current_device()}")
        print(f"Device name: {torch.cuda.get_device_name(torch.cuda.current_device())}")
    else:
        print("PyTorch is configured to run on CPU.")

except Exception as e:
    print(f"An error occurred: {e}")