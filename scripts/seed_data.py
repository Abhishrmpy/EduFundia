#!/usr/bin/env python3
"""
Seed data script for Smart Aid & Budget application.
Run with: python scripts/seed_data.py
"""

import asyncio
import uuid
from datetime import date, datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
import random

# Add parent directory to path
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.models.user import User, UserRole
from app.models.student import Student, CasteCategory, Gender
from app.models.expense import Expense, ExpenseCategory, PaymentMethod
from app.models.budget import Budget, BudgetStatus, BudgetPeriod
from app.models.scholarship import Scholarship, ScholarshipType, ScholarshipStatus
from app.models.notification import Notification, NotificationType, NotificationPriority


async def seed_database():
    """Seed the database with initial data"""
    print("🚀 Starting database seeding...")
    
    # Create engine and session
    engine = create_async_engine(str(settings.database_url))
    AsyncSessionLocal = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with AsyncSessionLocal() as session:
        try:
            # Check if data already exists
            result = await session.execute(select(User).limit(1))
            existing_user = result.scalar_one_or_none()
            
            if existing_user:
                print("⚠️  Database already has data. Skipping seeding.")
                return
            
            print("📦 Seeding users and students...")
            
            # Create admin user
            admin_user = User(
                firebase_uid="admin_firebase_uid_001",
                email="admin@smartaid.com",
                full_name="Admin User",
                phone_number="+919876543210",
                role=UserRole.ADMIN,
                email_verified=True,
                profile_completed=True
            )
            session.add(admin_user)
            await session.flush()
            
            # Create test students
            students_data = [
                {
                    "name": "Rahul Sharma",
                    "email": "rahul.sharma@college.com",
                    "phone": "+919876543211",
                    "enrollment": "COLL2024001",
                    "university": "Delhi University",
                    "college": "St. Stephen's College",
                    "course": "B.Sc Computer Science",
                    "year": 2,
                    "caste": CasteCategory.GENERAL,
                    "gender": Gender.MALE,
                    "income": 800000,
                    "allowance": 10000
                },
                {
                    "name": "Priya Patel",
                    "email": "priya.patel@college.com",
                    "phone": "+919876543212",
                    "enrollment": "COLL2024002",
                    "university": "University of Mumbai",
                    "college": "St. Xavier's College",
                    "course": "B.Com",
                    "year": 3,
                    "caste": CasteCategory.OBC,
                    "gender": Gender.FEMALE,
                    "income": 500000,
                    "allowance": 8000
                },
                {
                    "name": "Amit Kumar",
                    "email": "amit.kumar@college.com",
                    "phone": "+919876543213",
                    "enrollment": "COLL2024003",
                    "university": "IIT Delhi",
                    "college": "IIT Delhi",
                    "course": "B.Tech Computer Science",
                    "year": 1,
                    "caste": CasteCategory.SC,
                    "gender": Gender.MALE,
                    "income": 300000,
                    "allowance": 5000
                },
                {
                    "name": "Sneha Reddy",
                    "email": "sneha.reddy@college.com",
                    "phone": "+919876543214",
                    "enrollment": "COLL2024004",
                    "university": "Osmania University",
                    "college": "Nizam College",
                    "course": "MBBS",
                    "year": 2,
                    "caste": CasteCategory.GENERAL,
                    "gender": Gender.FEMALE,
                    "income": 1200000,
                    "allowance": 15000
                }
            ]
            
            created_students = []
            for i, student_data in enumerate(students_data):
                # Create user
                user = User(
                    firebase_uid=f"test_firebase_uid_{i+1}",
                    email=student_data["email"],
                    full_name=student_data["name"],
                    phone_number=student_data["phone"],
                    role=UserRole.STUDENT,
                    email_verified=True,
                    profile_completed=True
                )
                session.add(user)
                await session.flush()
                
                # Create student profile
                student = Student(
                    user_id=user.id,
                    enrollment_number=student_data["enrollment"],
                    university_name=student_data["university"],
                    college_name=student_data["college"],
                    course_name=student_data["course"],
                    course_duration=4 if student_data["course"] != "MBBS" else 5,
                    current_year=student_data["year"],
                    date_of_birth=date(2000 + i, 1, 15),
                    gender=student_data["gender"],
                    caste_category=student_data["caste"],
                    permanent_address=f"Address {i+1}, City, State",
                    current_address=f"Hostel {i+1}, College Campus",
                    city="Delhi" if i % 2 == 0 else "Mumbai",
                    state="Delhi" if i % 2 == 0 else "Maharashtra",
                    pincode="110001" if i % 2 == 0 else "400001",
                    guardian_name=f"Guardian {student_data['name']}",
                    guardian_phone=f"+91987654{3210 + i}",
                    guardian_relationship="Father",
                    family_annual_income=student_data["income"],
                    monthly_allowance=student_data["allowance"],
                    has_education_loan=i % 3 == 0,
                    education_loan_amount=student_data["income"] * 0.5 if i % 3 == 0 else None,
                    profile_completed=True,
                    profile_completed_at=datetime.utcnow(),
                    current_cgpa=random.uniform(7.5, 9.5),
                    last_semester_percentage=random.uniform(75, 95)
                )
                session.add(student)
                await session.flush()
                created_students.append((user, student))
            
            print("📊 Seeding expenses...")
            
            # Create expenses for each student
            expense_categories = list(ExpenseCategory)
            payment_methods = list(PaymentMethod)
            
            for user, student in created_students:
                for day_offset in range(90):  # Last 90 days
                    expense_date = date.today() - timedelta(days=day_offset)
                    
                    # Create 1-3 expenses per day
                    for _ in range(random.randint(1, 3)):
                        category = random.choice(expense_categories)
                        amount = random.uniform(50, 2000)
                        
                        expense = Expense(
                            user_id=user.id,
                            student_id=student.id,
                            title=f"{category.value.replace('_', ' ').title()} Expense",
                            description=f"Daily {category.value} expense",
                            category=category,
                            amount=amount,
                            payment_method=random.choice(payment_methods),
                            expense_date=expense_date,
                            location=student.city,
                            city=student.city,
                            tags=["daily", "essential"] if category in [
                                ExpenseCategory.FOOD, ExpenseCategory.TRANSPORT
                            ] else ["miscellaneous"]
                        )
                        session.add(expense)
            
            print("💰 Seeding budgets...")
            
            # Create budgets for each student
            for user, student in created_students:
                for month_offset in range(3):  # Last 3 months
                    start_date = date.today().replace(day=1) - timedelta(days=30 * month_offset)
                    end_date = (start_date + timedelta(days=30)).replace(day=1) - timedelta(days=1)
                    
                    total_amount = student.monthly_allowance or 10000
                    categories = {
                        "food": total_amount * 0.3,
                        "transport": total_amount * 0.2,
                        "books": total_amount * 0.15,
                        "entertainment": total_amount * 0.1,
                        "medical": total_amount * 0.05,
                        "other": total_amount * 0.2
                    }
                    
                    budget = Budget(
                        user_id=user.id,
                        student_id=student.id,
                        name=f"Monthly Budget - {start_date.strftime('%B %Y')}",
                        description=f"Budget for {start_date.strftime('%B %Y')}",
                        total_amount=total_amount,
                        spent_amount=total_amount * random.uniform(0.6, 1.2),
                        remaining_amount=max(0, total_amount - (total_amount * random.uniform(0.6, 1.2))),
                        categories=categories,
                        period=BudgetPeriod.MONTHLY,
                        start_date=start_date,
                        end_date=end_date,
                        status=BudgetStatus.ACTIVE if month_offset == 0 else BudgetStatus.COMPLETED,
                        ai_generated=random.choice([True, False])
                    )
                    session.add(budget)
            
            print("🎓 Seeding scholarships...")
            
            # Create scholarships
            scholarships_data = [
                {
                    "name": "National Merit Scholarship",
                    "type": ScholarshipType.GOVERNMENT,
                    "provider": "Ministry of Education",
                    "amount": 50000,
                    "min_income": 0,
                    "max_income": 800000,
                    "castes": ["general", "obc", "sc", "st", "ews"],
                    "courses": ["B.Tech", "MBBS", "B.Sc", "B.Com"],
                    "states": ["All India"]
                },
                {
                    "name": "SC/ST Scholarship",
                    "type": ScholarshipType.GOVERNMENT,
                    "provider": "Social Justice Ministry",
                    "amount": 30000,
                    "min_income": 0,
                    "max_income": 500000,
                    "castes": ["sc", "st"],
                    "courses": ["All Courses"],
                    "states": ["All India"]
                },
                {
                    "name": "Girl Child Scholarship",
                    "type": ScholarshipType.STATE,
                    "provider": "Delhi Government",
                    "amount": 25000,
                    "min_income": 0,
                    "max_income": 600000,
                    "genders": ["female"],
                    "courses": ["All Courses"],
                    "states": ["Delhi"]
                },
                {
                    "name": "Engineering Excellence Scholarship",
                    "type": ScholarshipType.PRIVATE,
                    "provider": "Tech Giants Foundation",
                    "amount": 75000,
                    "min_percentage": 85,
                    "courses": ["B.Tech Computer Science", "B.Tech Mechanical"],
                    "states": ["All India"]
                },
                {
                    "name": "Medical Aspirants Scholarship",
                    "type": ScholarshipType.UNIVERSITY,
                    "provider": "AIIMS Delhi",
                    "amount": 100000,
                    "min_percentage": 90,
                    "courses": ["MBBS"],
                    "states": ["All India"]
                }
            ]
            
            for i, scholarship_data in enumerate(scholarships_data):
                start_date = date.today() - timedelta(days=30)
                end_date = date.today() + timedelta(days=random.randint(30, 180))
                
                scholarship = Scholarship(
                    name=scholarship_data["name"],
                    description=f"{scholarship_data['name']} for deserving students",
                    scholarship_type=scholarship_data["type"],
                    provider_name=scholarship_data["provider"],
                    amount=scholarship_data["amount"],
                    eligibility_criteria={
                        "description": f"Eligibility criteria for {scholarship_data['name']}",
                        "requirements": ["Valid student ID", "Income certificate", "Marksheets"]
                    },
                    min_income=scholarship_data.get("min_income"),
                    max_income=scholarship_data.get("max_income"),
                    eligible_castes=scholarship_data.get("castes"),
                    eligible_genders=scholarship_data.get("genders"),
                    eligible_courses=scholarship_data["courses"],
                    eligible_states=scholarship_data["states"],
                    min_percentage=scholarship_data.get("min_percentage"),
                    application_start_date=start_date,
                    application_end_date=end_date,
                    result_date=end_date + timedelta(days=30),
                    status=ScholarshipStatus.ACTIVE,
                    is_featured=i < 2  # First 2 are featured
                )
                session.add(scholarship)
            
            print("🔔 Seeding notifications...")
            
            # Create notifications for each user
            notification_types = list(NotificationType)
            priorities = list(NotificationPriority)
            
            for user, student in created_students:
                for _ in range(random.randint(5, 15)):
                    notif_type = random.choice(notification_types)
                    priority = random.choice(priorities)
                    
                    notification = Notification(
                        user_id=user.id,
                        title=f"{notif_type.value.replace('_', ' ').title()}",
                        message=f"This is a sample {notif_type.value} notification for {user.full_name}",
                        notification_type=notif_type,
                        priority=priority,
                        is_read=random.choice([True, False]),
                        is_sent=True,
                        sent_at=datetime.utcnow() - timedelta(days=random.randint(0, 30)),
                        created_at=datetime.utcnow() - timedelta(days=random.randint(0, 30))
                    )
                    session.add(notification)
            
            # Commit all changes
            await session.commit()
            print("✅ Database seeding completed successfully!")
            
        except Exception as e:
            await session.rollback()
            print(f"❌ Database seeding failed: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(seed_database())