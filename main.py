import os
import base64
import markdown
from openai import OpenAI
from pdf2image import convert_from_path
from io import BytesIO
from flask import Flask, render_template, request, redirect, url_for, flash, session, make_response
from form import EditForm
from flask_ckeditor import CKEditor
from datetime import datetime, timedelta
from xhtml2pdf import pisa

app = Flask(__name__)
ckeditor = CKEditor(app)

UPLOAD_FOLDER = 'static/asset/'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SECRET_KEY']= os.environ.get("SECRET_KEY")

# Set session lifetime to 60 minutes
app.permanent_session_lifetime = timedelta(minutes=60)

client = OpenAI(
    api_key=os.environ.get("OPENAI_DISCHARGE_API")
)

def generate_unique_filename():
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"{timestamp}.pdf"

encoded_images = []

# convert pdf file to a list of images
def pdf_to_encoded_imgs(pdf_path):
    global encoded_images
    images = convert_from_path(pdf_path)

    encoded_images = []  # Clear the list before appending new images

    for image in images:
        # convert image to bytes
        buffered = BytesIO()
        image.save(buffered, format='JPEG')

        # encode the image to Base64
        img_str = base64.b64encode(buffered.getvalue()).decode()

        # append the encoded string to the list
        encoded_images.append(img_str)

    return encoded_images

def send_request(encoded_images, custom_prompt):
    # send request to ChatGPT
    response = client.chat.completions.create(
        model="gpt-4-vision-preview",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": custom_prompt,
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{encoded_images[0]}",
                        },
                    },
                ],
            }
        ],
        max_tokens=4000,
    )

    return response.choices[0].message.content


@app.route("/", methods=['GET', 'POST'])
def home():
    global encoded_images
    if request.method == 'POST':
        if 'pdf' not in request.files:
            flash('No file part')
            return redirect(url_for('home'))
        file  = request.files['pdf']
        if file.filename == '':
            flash('No selected file')
            return redirect(url_for('home'))
        if file and file.filename.endswith('.pdf'):
            filename = generate_unique_filename()
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            encoded_images = pdf_to_encoded_imgs(f'static/asset/{filename}')
            return redirect(url_for('get_clinic'))
    return render_template('index.html')

@app.route("/clinic", methods=['GET', 'POST'])
def get_clinic():
    global encoded_images
    content = send_request(encoded_images, clinical_prompt)
    content = content.replace('\n', '<br>')
    content = markdown.markdown(content)
    session['content'] = content
    session['is_clinic'] = True
    return redirect(url_for('get_summary'))

@app.route('/patient-friendly', methods=['GET', 'POST'])
def get_patient_friendly():
    global encoded_images
    content = send_request(encoded_images, patient_friendly_prompt)
    content = content.replace('\n', '<br>')
    content = markdown.markdown(content)
    session['content'] = content
    session['is_clinic'] = False
    return redirect(url_for('get_summary'))

@app.route("/summary", methods=['GET', 'POST'])
def get_summary():
    content = session.get('content', None)
    is_clinic = session.get('is_clinic', None)
    return render_template('edit.html', content=content, is_edit=False, is_clinic=is_clinic)

@app.route("/edit", methods=['GET', 'POST'])
def edit():
    content = session.get('content', None)
    form = EditForm(
        body = content
    )
    if form.validate_on_submit():
        content = form.body.data
        session['content'] = content
        flash("You've updated the discharge summary")
        return redirect(url_for('get_summary'))
    return render_template('edit.html', is_edit=True, form=form, content=content)

@app.route('/download', methods=['GET'])
def download_pdf():
    content = session.get('content', None)
    if content:
        # Convert HTML content to PDF using xhtml2pdf
        pdf_data = generate_pdf(content)
        if pdf_data:
            response = make_response(pdf_data)
            response.headers['Content-Type'] = 'application/pdf'
            response.headers['Content-Disposition'] = 'attachment; filename=discharge_summary.pdf'
            return response
        else:
            flash('Failed to generate PDF.')
    else:
        flash('No content available for download.')
    return redirect(url_for('get_summary'))

# Define patient friendly prompt and clinical prompt
patient_friendly_prompt = ("Given a set of clinical notes from a patient's medical record, produce a clear and concise medical discharge summary. The summary should succinctly include the following core components:\n\n"
                        "1. Reason for Admission: Summarize the primary cause or event leading to the patient's hospitalization.\n"
                        "2. Key Investigations and Results: Summarize important diagnostic tests conducted during the hospital stay and their outcomes and why they were done.\n"
                        "3. Procedures Performed: Briefly list any medical or surgical procedures the patient underwent during their stay, highlight why this was done.\n"
                        "4. Primary and Secondary Diagnoses: Briefly state the main and any secondary diagnoses made during the hospitalization.\n"
                        "5. Medication Changes: Note any changes to the patient's medication regimen during their stay and why these were done.\n"
                        "6. Plan for Follow-Up: Include briefly appointments, tests, or treatments scheduled after discharge for ongoing care as mention in the clinical notes.\n"
                        "The summary generated should be presented to a non-medical patient in second person, avoid formatting the summary as a letter. Therefore, medical jargon should be explained succinctly within a parenthesis next to the medical term. This should be easy to understand but not lack detail on what term or procedure is being explained."
                        "Please generate the core components into 6 short concise paragraphs. The discharge summary should be legible and easy to read. Keep this summary specific to the patient and do not omit any important details from the original clinical note such as diagnosis, values from tests and procedures, reasons for medication changes, plans for follow up.")

clinical_prompt = ("Given a set of clinical notes from a patients medical record, produce a clear and concise medical discharge summary. The summary should succinctly include the following 10 core components:\n\n"
            "1. Reason for Admission: Summarize the primary cause or event leading to the patient's hospitalization.\n"
            "2. Relevant Past Medical and Surgical History: Include any significant past illnesses and surgeries that are pertinent to the current condition.\n"
            "3. Social Context: Outline the patient's social situation, including smoking and alcohol history, family, living conditions, and support systems, if relevant.\n"
            "4. Key Investigations and Results: Detail important diagnostic tests conducted during the hospital stay and their outcomes.\n"
            "5. Procedures Performed: List any medical or surgical procedures the patient underwent during their stay.\n"
            "6. Primary and Secondary Diagnoses: State the main and any secondary diagnoses made during the hospitalization.\n"
            "7. Medication Changes: Note any changes to the patient's medication regimen during their stay. Highlight why the medication has been changed\n"
            "8. Medications to be Reviewed by the GP: Identify medications that require follow-up or review by the general practitioner.\n"
            "9. GP Actions Following Discharge: Specify actions or monitoring the GP should undertake post-discharge.\n"
            "10. Plan for Follow-Up: Include appointments, tests, or treatments scheduled after discharge for ongoing care.\n"
            "Organize the summary with 10 clear headings for each core component, ensure there are sub-bullet points with clear and concise information, maintaining the clarity and brevity of the discharge summary.\n"
            "Please also ensure that the summary highlights What the plan is for the patient post discharge, including any follow-up appointments, changes to medication, tests, or treatments that are scheduled.")

def generate_pdf(html_content):
    buffer = BytesIO()
    pisa_status = pisa.CreatePDF(html_content, dest=buffer)
    if pisa_status.err:
        return None
    else:
        pdf_data = buffer.getvalue()
        buffer.close()
        return pdf_data

https://github.com/ksu-hmi/deanna.AI.discharge.summaries/blob/main/SMS

if __name__ == '__main__':
    app.run(debug=True, port=5000)
