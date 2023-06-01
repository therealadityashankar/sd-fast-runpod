''' infer.py for runpod worker '''

import os
import predict
import argparse

import runpod
from runpod.serverless.utils.rp_validator import validate
from runpod.serverless.utils.rp_upload import upload_file_to_bucket
from runpod.serverless.utils import rp_download, rp_cleanup

from rp_schema import INPUT_SCHEMA


def run(job):
    '''
    Run inference on the model.
    Returns output path, width the seed used to generate the image.
    '''
    job_input = job['input']

    # Input validation
    validated_input = validate(job_input, INPUT_SCHEMA)

    if 'errors' in validated_input:
        return {"error": validated_input['errors']}
    validated_input = validated_input['validated_input']

    # Download input objects
    validated_input['init_image'], validated_input['mask'] = rp_download.download_files_from_urls(
        job['id'],
        [validated_input.get('init_image', None), validated_input.get(
            'mask', None)]
    )  # pylint: disable=unbalanced-tuple-unpacking

    MODEL.NSFW = validated_input.get('nsfw', True)

    if validated_input['seed'] is None:
        validated_input['seed'] = int.from_bytes(os.urandom(2), "big")

    img_paths = MODEL.predict(
        prompt=validated_input["prompt"],
        negative_prompt=validated_input.get("negative_prompt", None),
        width=validated_input.get('width', 512),
        height=validated_input.get('height', 512),
        init_image=validated_input['init_image'],
        mask=validated_input['mask'],
        prompt_strength=validated_input['prompt_strength'],
        num_outputs=validated_input.get('num_outputs', 1),
        num_inference_steps=validated_input.get('num_inference_steps', 50),
        guidance_scale=validated_input['guidance_scale'],
        scheduler=validated_input.get('scheduler', "K-LMS"),
        lora=validated_input.get("lora", None),
        lora_scale=validated_input.get("lora_scale", 1),
        seed=validated_input['seed']
    )

    job_output = []
    for index, img_path in enumerate(img_paths):
        file_name = f"{job['id']}_{index}.png"
        image_url = upload_file_to_bucket(file_name, img_path)

        job_output.append({
            "image": image_url,
            "seed": validated_input['seed'] + index
        })

    # Remove downloaded input objects
    rp_cleanup.clean(['input_objects'])

    return job_output


# Grab args
parser = argparse.ArgumentParser()
parser.add_argument('--model_tag', type=str, default="runwayml/stable-diffusion-v1-5")

if __name__ == "__main__":
    args = parser.parse_args()

    MODEL = predict.Predictor(model_tag=args.model_tag)
    MODEL.setup()

    runpod.serverless.start({"handler": run})