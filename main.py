import os 
import base64
import markdown
from openai import OpenAI
from pdf2image import convert_from_path
from io import BytesIO
from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)

client = OpenAI(
    api_key=os.environ.get("OPENAI_DISCHARGE_API")
)



# convert pdf file to a list of images 
def pdf_to_encoded_imgs(pdf_path):
    images = convert_from_path(pdf_path)

    # list to hold base64 encoded images
    encoded_images = []

    for image in images:
        # convert image to bytes
        buffered = BytesIO()
        image.save(buffered, format='JPEG')

        # encode the image to Base64
        img_str = base64.b64encode(buffered.getvalue()).decode()

        # append the encoded string to the list
        encoded_images.append(img_str) # encoded_images contains all the pages of the PDF as Base64 encoded strings
        print(len(encoded_images))
        return encoded_images

def send_request(encoded_images):
    # send request to ChatGPT
    response = client.chat.completions.create(
    model="gpt-4-vision-preview",
    messages=[
        {
        "role": "user",
        "content": [
            {
            "type": "text",
            "text": "You're an experienced doctor. These images are the medical notes from a fake patient. Based on the medical notes, You need to generate a discharge summary for this fake patient.",
            },
            {
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{encoded_images[0]}",
            },
            },
            # {
            # "type": "image_url",
            # "image_url": {
            #     "url": f"data:image/jpeg;base64,{encoded_images[1]}",
            # },
            # },
        ],
        }
    ],
    max_tokens=1000,
    )

    return response.choices[0].message.content


@app.route("/", methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        if 'pdf' not in request.files:
            return redirect(url_for('home'))
        file  = request.files['pdf']
        if file.filename == '':
            return render_template('index.html', headline='No selected file')
        if file and file.filename.endswith('.pdf'):
            file.save('asset/example.pdf')
            encoded_images = pdf_to_encoded_imgs('asset/example.pdf')
            content = markdown.markdown(send_request(encoded_images))            
            return render_template('summary.html', content=content)
    return render_template('index.html', headline='Upload your medical notes.')


if __name__ == '__main__':
    app.run(debug=True, port=5000)