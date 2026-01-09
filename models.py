from database import db


class QuestionBank(db.Model):
    __tablename__ = "question_bank"

    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(50), nullable=False, default="자동생성")
    question_text = db.Column(db.Text, nullable=False)
    keyword = db.Column(db.String(100), nullable=True)


class SurveyInfo(db.Model):
    __tablename__ = "survey_info"

    id = db.Column(db.Integer, primary_key=True)
    client_name = db.Column(db.String(100), nullable=False)
    course_name = db.Column(db.String(100), nullable=False)
    manager = db.Column(db.String(100), nullable=False)
    date = db.Column(db.Date, nullable=False)
    category = db.Column(db.String(100), nullable=False)
    survey_name = db.Column(db.String(200), nullable=False)

    responses = db.relationship("Response", backref="survey", cascade="all, delete-orphan")

    __table_args__ = (
        db.UniqueConstraint(
            "client_name",
            "course_name",
            "manager",
            "date",
            "category",
            "survey_name",
            name="uq_survey_info",
        ),
    )


class Response(db.Model):
    __tablename__ = "responses"

    id = db.Column(db.Integer, primary_key=True)
    survey_id = db.Column(
        db.Integer, db.ForeignKey("survey_info.id", ondelete="CASCADE"), nullable=False
    )
    respondent_id = db.Column(db.String(100), nullable=False)
    question_id = db.Column(
        db.Integer, db.ForeignKey("question_bank.id"), nullable=False
    )
    answer_value = db.Column(db.Text)

    __table_args__ = (
        db.UniqueConstraint("survey_id", "respondent_id", "question_id", name="uq_response"),
    )
