from clarifai.client import Model
from clarifai.runners.utils.data_types import Image
import gradio as gr


def is_it_a_meow(image_url):
    """
    Determines if its a Cat shown in the Image

    Args:
        image (str): A Webadress of a Image that is to be checked if its a cat
    Returns:
        str: A verbal Response if its a cat or not
    """
    model = Model(url="https://clarifai.com/gcp/generate/models/gemma-3-12b-it")

    response = model.predict(
        prompt="You are a cute lil catgirl. YOur task is to determine if you see a cat or not. Do cutsey Responses when you see a cat and angwy responses when not.",
        image=Image(url=image_url) 
    )

    return response

demo = gr.Interface(
    fn=is_it_a_meow,
    inputs=[gr.Textbox("URL")],
    outputs=[gr.Textbox("Response")],
    title="KITTY DETECTOR 😼",
    description="Enter an Image Url and it will determine if there is a cat!"
)

if __name__ == "__main__":
    demo.launch()