"""Experiment on how image transformations affect similarity.

How do simple transformations (e.g. scaling, rotation, jittering) impact similarity?
It turns out that most of them still keep high 90s similarity.
"""

import argparse
import warnings
from typing import Any

import torch
from PIL import Image
from torch import nn
from torch.nn.functional import cosine_similarity
from torchvision import models, transforms


def get_embedding(model: nn.Sequential, tensor: torch.Tensor) -> torch.Tensor:
    with torch.no_grad():
        embedding = model(tensor)
    return embedding.squeeze()


def preprocess(image: Any) -> torch.Tensor:
    """Preprocess with transforms.Compose: resize, crop and normalise.

    This function is a type-safe wrapper. It doesn't have change the beahaviour.
    """
    return transforms.Compose(
        [
            transforms.Resize(256),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ]
    )(image)


def main(image_path: str) -> None:
    warnings.filterwarnings(
        "ignore", category=UserWarning, module="torchvision.models._utils"
    )

    image_original = Image.open(image_path)
    tensor_original = preprocess(image_original).unsqueeze(0)

    transformations = {
        # Define transformations using RandomRotation with fixed degrees
        "Rotate_15": transforms.Compose([transforms.RandomRotation((15, 15))]),
        "Rotate_30": transforms.Compose([transforms.RandomRotation((30, 30))]),
        "Rotate_60": transforms.Compose([transforms.RandomRotation((60, 60))]),
        "Rotate_90": transforms.Compose([transforms.RandomRotation((90, 90))]),
        # Other random transformations
        "Horizontal_Flip": transforms.Compose([transforms.RandomHorizontalFlip(p=1.0)]),
        "Color_Jitter": transforms.Compose([transforms.ColorJitter(brightness=0.5)]),
        "Gaussian_Blur": transforms.Compose(
            [transforms.GaussianBlur(kernel_size=(5, 9), sigma=(0.1, 5))]
        ),
        # Scaling
        "Scale_80%": transforms.Compose([transforms.Resize(int(224 * 0.8))]),
        "Scale_120%": transforms.Compose([transforms.Resize(int(224 * 1.2))]),
        "Scale_200%": transforms.Compose([transforms.Resize(int(224 * 2))]),
    }

    model_original = models.resnet50(pretrained=True)
    model_embedding = nn.Sequential(*list(model_original.children())[:-1]).eval()

    embedding_original = get_embedding(model_embedding, tensor_original)

    similarities: dict[str, float] = {}
    for name, transform in transformations.items():
        image_transformed = transform(image_original).resize(
            (224, 224)
        )  # Ensure consistent size
        tensor_transformed = preprocess(image_transformed).unsqueeze(0)
        embedding_transformed = get_embedding(model_embedding, tensor_transformed)

        similarities[name] = cosine_similarity(
            embedding_original, embedding_transformed, dim=0
        ).item()

    header_name, header_sim = "Transformation", "Similarity"
    w = max(*(len(n) for n in similarities), len(header_name), 20)
    print(f"{header_name:<{w}} {header_sim}")
    for n, s in sorted(similarities.items(), key=lambda x: x[1], reverse=True):
        print(f"{n:<{w}} {s:.4f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("image_path", type=str, help="Path to the image")
    args = parser.parse_args()
    main(args.image_path)
