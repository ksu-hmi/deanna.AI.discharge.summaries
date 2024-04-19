from flask_wtf import FlaskForm
from wtforms.validators import DataRequired
from flask_ckeditor import CKEditorField


class EditForm(FlaskForm):
    body = CKEditorField('Edit Discharge Summary', validators=[DataRequired()])

