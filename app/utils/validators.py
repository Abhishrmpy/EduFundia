import re
from typing import Optional, List
from datetime import date, datetime
import uuid


class Validators:
    """Validation utilities"""
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """Validate email format"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    @staticmethod
    def validate_phone(phone: str) -> bool:
        """Validate Indian phone number"""
        pattern = r'^(\+91[\-\s]?)?[6-9]\d{9}$'
        return bool(re.match(pattern, phone))
    
    @staticmethod
    def validate_pincode(pincode: str) -> bool:
        """Validate Indian pincode (6 digits)"""
        pattern = r'^\d{6}$'
        return bool(re.match(pattern, pincode))
    
    @staticmethod
    def validate_aadhar(aadhar: str) -> bool:
        """Validate Aadhar number (12 digits)"""
        pattern = r'^\d{12}$'
        return bool(re.match(pattern, aadhar))
    
    @staticmethod
    def validate_pan(pan: str) -> bool:
        """Validate PAN number"""
        pattern = r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$'
        return bool(re.match(pattern, pan))
    
    @staticmethod
    def validate_ifsc(ifsc: str) -> bool:
        """Validate IFSC code"""
        pattern = r'^[A-Z]{4}0[A-Z0-9]{6}$'
        return bool(re.match(pattern, ifsc))
    
    @staticmethod
    def validate_amount(amount: float, min_amount: float = 0, max_amount: float = 10000000) -> bool:
        """Validate amount within range"""
        return min_amount <= amount <= max_amount
    
    @staticmethod
    def validate_date_range(start_date: date, end_date: date) -> bool:
        """Validate date range"""
        return start_date <= end_date
    
    @staticmethod
    def validate_age(date_of_birth: date, min_age: int = 16, max_age: int = 35) -> bool:
        """Validate age range for students"""
        today = date.today()
        age = today.year - date_of_birth.year - ((today.month, today.day) < (date_of_birth.month, date_of_birth.day))
        return min_age <= age <= max_age
    
    @staticmethod
    def validate_uuid(uuid_str: str) -> bool:
        """Validate UUID string"""
        try:
            uuid.UUID(uuid_str)
            return True
        except ValueError:
            return False
    
    @staticmethod
    def validate_percentage(percentage: float) -> bool:
        """Validate percentage (0-100)"""
        return 0 <= percentage <= 100
    
    @staticmethod
    def validate_cgpa(cgpa: float) -> bool:
        """Validate CGPA (0-10)"""
        return 0 <= cgpa <= 10
    
    @staticmethod
    def validate_url(url: str) -> bool:
        """Validate URL"""
        pattern = r'^https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&\/=]*)$'
        return bool(re.match(pattern, url))
    
    @staticmethod
    def validate_file_extension(filename: str, allowed_extensions: List[str]) -> bool:
        """Validate file extension"""
        return any(filename.lower().endswith(ext.lower()) for ext in allowed_extensions)
    
    @staticmethod
    def validate_file_size(file_size: int, max_size_mb: int = 10) -> bool:
        """Validate file size"""
        max_size_bytes = max_size_mb * 1024 * 1024
        return file_size <= max_size_bytes
    
    @staticmethod
    def sanitize_input(input_str: str, max_length: int = 1000) -> str:
        """Sanitize user input"""
        if not input_str:
            return ""
        
        # Remove potentially dangerous characters
        sanitized = re.sub(r'[<>"\']', '', input_str)
        
        # Limit length
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length]
        
        return sanitized.strip()
    
    @staticmethod
    def validate_password_strength(password: str) -> dict:
        """Validate password strength"""
        result = {
            "valid": False,
            "score": 0,
            "feedback": []
        }
        
        if len(password) < 8:
            result["feedback"].append("Password must be at least 8 characters")
            return result
        
        score = 0
        
        # Check for uppercase
        if re.search(r'[A-Z]', password):
            score += 1
        else:
            result["feedback"].append("Add uppercase letters")
        
        # Check for lowercase
        if re.search(r'[a-z]', password):
            score += 1
        else:
            result["feedback"].append("Add lowercase letters")
        
        # Check for numbers
        if re.search(r'\d', password):
            score += 1
        else:
            result["feedback"].append("Add numbers")
        
        # Check for special characters
        if re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            score += 1
        else:
            result["feedback"].append("Add special characters")
        
        # Length bonus
        if len(password) >= 12:
            score += 1
        
        result["score"] = score
        result["valid"] = score >= 3
        
        if score >= 4:
            result["feedback"].append("Strong password")
        elif score >= 3:
            result["feedback"].append("Good password")
        else:
            result["feedback"].append("Weak password")
        
        return result
    
    @staticmethod
    def validate_income(income: float) -> bool:
        """Validate annual income (reasonable range for Indian students)"""
        return 0 <= income <= 100000000  # Max 10 crore
    
    @staticmethod
    def validate_course_name(course: str) -> bool:
        """Validate course name"""
        # Common Indian course patterns
        patterns = [
            r'^B\.?Tech',
            r'^B\.?E\.?',
            r'^MBBS',
            r'^B\.?Sc',
            r'^B\.?Com',
            r'^B\.?A',
            r'^M\.?Tech',
            r'^M\.?Sc',
            r'^M\.?A',
            r'^PhD',
            r'^Diploma',
        ]
        
        course_upper = course.upper()
        return any(re.match(pattern, course_upper) for pattern in patterns)


# Singleton instance
validators = Validators()