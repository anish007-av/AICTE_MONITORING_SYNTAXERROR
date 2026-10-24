import pytest
from datetime import datetime, timedelta
from extensions import db
from models.institution import Institution
from models.user import User
from models.complaint import Complaint
from models.overlap import OverlapRelationship
from models.group import RelatedComplaintGroup
from services.overlap_detection import calculate_overlap_score

def test_five_overlap_groups_detection_logic(db_session, sample_institution):
    """Verify that the AI overlap detector correctly identifies at least 5 distinct overlap groups
    matching the user specifications across different categories and phrasing.
    """
    groups_data = [
        # Group 1: Scholarship Delays
        (
            "Scholarship Delays",
            "Approved stipend disbursal pending",
            "Approved AICTE Pragati scholarship amount not credited for several months",
            "My approved AICTE Pragati technical scholarship funds have not been credited to my bank account for over four months despite completing all institutional biometric verifications.",
            "Repeated delays in disbursing sanctioned scholarship payment to students",
            "Several eligible female students at our institute report repeated delays in receiving sanctioned scholarship payments and welfare stipends for the current academic session.",
        ),
        # Group 2: Hostel Water Supply
        (
            "Hostel and Accommodation",
            "Hostel water supply disruption",
            "Irregular and disrupted water supply in hostel block C",
            "Students living in hostel block C report that our residential block has had irregular water supply for several days, leaving resident students with dry bathroom taps during peak morning preparation hours.",
            "Hostel block C running water stops every evening",
            "A resident reports that running tap water supply completely stops every evening in hostel block C, creating severe sanitation hardship for hostel students returning from evening lecture sessions.",
        ),
        # Group 3: Laboratory Equipment
        (
            "Laboratory Equipment and Infrastructure",
            "Mechanical lab testing equipment failure",
            "Essential tensile testing equipment in mechanical engineering laboratory not functioning",
            "Essential apparatus and universal testing machines in the mechanical engineering laboratory have been completely non-functional for three weeks without repair.",
            "Practical lab sessions disrupted because mechanical laboratory equipment is out of service",
            "Third-year engineering students report that practical laboratory sessions are disrupted and incomplete because the mechanical laboratory equipment remains out of service.",
        ),
        # Group 4: Examination Results
        (
            "Academic and Examination Issues",
            "Semester examination result publication delay",
            "Semester examination results not published despite official announced date",
            "A student reports that our end-semester examination results have not been published by the examination branch despite the official deadline announced on the academic calendar over three weeks ago.",
            "Multiple students from semester examination unable to access announced results",
            "Several students who appeared for the third-semester diploma examination report that they are still unable to access their examination results on the student portal due to database errors.",
        ),
        # Group 5: Classroom Infrastructure
        (
            "Laboratory Equipment and Infrastructure",
            "Classroom ventilation & fan maintenance",
            "Broken ceiling fans and poor ventilation in classroom 204",
            "Students report broken ceiling fans and poor ventilation in classroom 204, causing suffocating humidity and severe discomfort during afternoon lectures with sixty students enclosed.",
            "Classroom 204 excessively hot and stifling because ceiling fans are not working",
            "Another student reports that classroom 204 remains excessively hot and unbreathable during class hours because none of the ceiling fans are operational despite previous maintenance requests.",
        ),
    ]

    assert len(groups_data) == 5

    for idx, (cat, subcat, title_a, desc_a, title_b, desc_b) in enumerate(groups_data, start=1):
        ca = Complaint(
            title=title_a,
            description=desc_a,
            category=cat,
            subcategory=subcat,
            institution_id=sample_institution.id,
            status="Open",
            created_at=datetime.utcnow(),
        )
        cb = Complaint(
            title=title_b,
            description=desc_b,
            category=cat,
            subcategory=subcat,
            institution_id=sample_institution.id,
            status="Open",
            created_at=datetime.utcnow(),
        )
        res = calculate_overlap_score(ca, cb, allow_transformer=False)
        assert res["similarity_score"] >= 0.50, f"Group {idx} ({cat}) scored below 0.50: {res['similarity_score']}"
        assert res["relationship_type"] in ["Strong Potential Overlap", "Possible Overlap"]
        assert res["matching_evidence"] is not None


def test_dashboard_renders_suggested_overlap_groups(client, db_session, sample_institution, super_admin_user):
    """Verify that when suggested groups exist in database, officer dashboard displays them with controls."""
    # Create an overlap group
    grp = RelatedComplaintGroup(
        group_reference="AICTE-GRP-TEST-0001",
        title="Hostel Block C Chronic Water Shortage & Evening Supply Disruptions",
        category="Hostel and Accommodation",
        institution_id=sample_institution.id,
        status="Open",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(grp)
    db_session.flush()

    c1 = Complaint(
        reference_number="AICTE-TEST-CMP-001",
        title="Irregular water supply in hostel block C",
        description="Dry bathroom taps in hostel block C.",
        category="Hostel and Accommodation",
        subcategory="Hostel water supply disruption",
        institution_id=sample_institution.id,
        related_group_id=grp.id,
        status="Open",
    )
    c2 = Complaint(
        reference_number="AICTE-TEST-CMP-002",
        title="Hostel block C running water stops every evening",
        description="No water in evening hours in hostel block C.",
        category="Hostel and Accommodation",
        subcategory="Hostel water supply disruption",
        institution_id=sample_institution.id,
        related_group_id=grp.id,
        status="Open",
    )
    db_session.add_all([c1, c2])
    db_session.flush()

    # Create overlap relationship
    overlap = OverlapRelationship(
        first_complaint_id=min(c1.id, c2.id),
        second_complaint_id=max(c1.id, c2.id),
        similarity_score=0.74,
        semantic_score=0.55,
        keyword_score=0.60,
        category_score=1.0,
        context_score=0.85,
        relationship_type="Possible Overlap",
        review_status="Pending Review",
        matching_evidence='{"summary": "Test evidence"}',
        created_at=datetime.utcnow(),
    )
    db_session.add(overlap)
    db_session.commit()

    # Login as super admin
    login_res = client.post("/login", data={
        "username": "admin_test",
        "password": "AdminPass123",
        "selected_institution_id": "1"
    }, follow_redirects=True)
    assert login_res.status_code == 200

    dash_res = client.get("/dashboard")
    assert dash_res.status_code == 200
    html = dash_res.data.decode("utf-8")

    assert "Suggested Complaint Overlap Groups" in html
    assert "AICTE-GRP-TEST-0001" in html
    assert "Pending Verification" in html
    assert "Confirm Overlap" in html
    assert "Reject Overlap" in html


def test_human_confirmation_and_rejection_workflow(client, db_session, sample_institution, super_admin_user):
    """Verify that an officer can confirm and reject an overlap, persisting the result."""
    grp = RelatedComplaintGroup(
        group_reference="AICTE-GRP-TEST-0002",
        title="Mechanical Engineering Lab Tensile Testing Breakdown",
        category="Laboratory Equipment and Infrastructure",
        institution_id=sample_institution.id,
        status="Open",
    )
    db_session.add(grp)
    db_session.flush()

    c1 = Complaint(
        reference_number="AICTE-TEST-CMP-003",
        title="Lab machines broken in mechanical department",
        description="Testing apparatus non functional in mechanical lab.",
        category="Laboratory Equipment and Infrastructure",
        institution_id=sample_institution.id,
        related_group_id=grp.id,
        status="Open",
    )
    c2 = Complaint(
        reference_number="AICTE-TEST-CMP-004",
        title="Practical experiments disrupted due to broken lab machines",
        description="Students cannot perform experiments in mechanical lab.",
        category="Laboratory Equipment and Infrastructure",
        institution_id=sample_institution.id,
        related_group_id=grp.id,
        status="Open",
    )
    db_session.add_all([c1, c2])
    db_session.flush()

    overlap = OverlapRelationship(
        first_complaint_id=min(c1.id, c2.id),
        second_complaint_id=max(c1.id, c2.id),
        similarity_score=0.72,
        semantic_score=0.50,
        keyword_score=0.55,
        category_score=1.0,
        context_score=0.85,
        relationship_type="Possible Overlap",
        review_status="Pending Review",
        matching_evidence='{"summary": "Test evidence"}',
    )
    db_session.add(overlap)
    db_session.commit()

    # Login
    client.post("/login", data={
        "username": "admin_test",
        "password": "AdminPass123",
        "selected_institution_id": "1"
    }, follow_redirects=True)

    # 1. Confirm Overlap
    res_confirm = client.post(f"/overlaps/{overlap.id}/review", data={
        "action": "confirm",
        "review_notes": "Official AICTE verification note"
    }, follow_redirects=True)
    assert res_confirm.status_code == 200

    db_session.refresh(overlap)
    assert overlap.review_status == "Confirmed Related"
    assert overlap.relationship_type == "Human-Confirmed Related"
    assert overlap.reviewer_id == super_admin_user.id
    assert "Official AICTE verification note" in overlap.review_notes

    # 2. Reject Overlap
    res_reject = client.post(f"/overlaps/{overlap.id}/review", data={
        "action": "reject",
        "review_notes": "Official AICTE rejection note"
    }, follow_redirects=True)
    assert res_reject.status_code == 200

    db_session.refresh(overlap)
    assert overlap.review_status == "Rejected Not Related"
    assert overlap.relationship_type == "Human-Confirmed Not Related"

    # 3. Reset Overlap
    res_reset = client.post(f"/overlaps/{overlap.id}/review", data={
        "action": "reset",
    }, follow_redirects=True)
    assert res_reset.status_code == 200

    db_session.refresh(overlap)
    assert overlap.review_status == "Pending Review"
