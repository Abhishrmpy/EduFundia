from datetime import datetime, date, timedelta
from typing import List, Tuple, Optional
import calendar
import pytz


class DateUtils:
    """Date and time utilities"""
    
    # Indian timezone
    IST = pytz.timezone('Asia/Kolkata')
    
    @staticmethod
    def get_current_datetime() -> datetime:
        """Get current datetime in IST"""
        return datetime.now(DateUtils.IST)
    
    @staticmethod
    def get_current_date() -> date:
        """Get current date in IST"""
        return DateUtils.get_current_datetime().date()
    
    @staticmethod
    def format_datetime(dt: datetime, format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
        """Format datetime to string"""
        if dt.tzinfo is None:
            dt = DateUtils.IST.localize(dt)
        return dt.strftime(format_str)
    
    @staticmethod
    def parse_datetime(datetime_str: str, format_str: str = "%Y-%m-%d %H:%M:%S") -> Optional[datetime]:
        """Parse string to datetime"""
        try:
            dt = datetime.strptime(datetime_str, format_str)
            return DateUtils.IST.localize(dt)
        except ValueError:
            return None
    
    @staticmethod
    def format_date(d: date, format_str: str = "%Y-%m-%d") -> str:
        """Format date to string"""
        return d.strftime(format_str)
    
    @staticmethod
    def parse_date(date_str: str, format_str: str = "%Y-%m-%d") -> Optional[date]:
        """Parse string to date"""
        try:
            return datetime.strptime(date_str, format_str).date()
        except ValueError:
            return None
    
    @staticmethod
    def get_days_between(start_date: date, end_date: date) -> int:
        """Get number of days between two dates"""
        return (end_date - start_date).days
    
    @staticmethod
    def add_days(to_date: date, days: int) -> date:
        """Add days to a date"""
        return to_date + timedelta(days=days)
    
    @staticmethod
    def subtract_days(from_date: date, days: int) -> date:
        """Subtract days from a date"""
        return from_date - timedelta(days=days)
    
    @staticmethod
    def get_start_of_month(d: date = None) -> date:
        """Get start date of month"""
        if d is None:
            d = DateUtils.get_current_date()
        return date(d.year, d.month, 1)
    
    @staticmethod
    def get_end_of_month(d: date = None) -> date:
        """Get end date of month"""
        if d is None:
            d = DateUtils.get_current_date()
        _, last_day = calendar.monthrange(d.year, d.month)
        return date(d.year, d.month, last_day)
    
    @staticmethod
    def get_start_of_week(d: date = None) -> date:
        """Get start of week (Monday)"""
        if d is None:
            d = DateUtils.get_current_date()
        return d - timedelta(days=d.weekday())
    
    @staticmethod
    def get_end_of_week(d: date = None) -> date:
        """Get end of week (Sunday)"""
        if d is None:
            d = DateUtils.get_current_date()
        start = DateUtils.get_start_of_week(d)
        return start + timedelta(days=6)
    
    @staticmethod
    def get_date_range(start_date: date, end_date: date) -> List[date]:
        """Get list of dates between start and end (inclusive)"""
        dates = []
        current = start_date
        while current <= end_date:
            dates.append(current)
            current += timedelta(days=1)
        return dates
    
    @staticmethod
    def get_month_name(month_number: int) -> str:
        """Get month name from month number"""
        return calendar.month_name[month_number]
    
    @staticmethod
    def get_short_month_name(month_number: int) -> str:
        """Get short month name from month number"""
        return calendar.month_abbr[month_number]
    
    @staticmethod
    def is_weekday(d: date) -> bool:
        """Check if date is a weekday (Monday-Friday)"""
        return d.weekday() < 5
    
    @staticmethod
    def is_weekend(d: date) -> bool:
        """Check if date is a weekend (Saturday-Sunday)"""
        return d.weekday() >= 5
    
    @staticmethod
    def get_working_days(start_date: date, end_date: date) -> int:
        """Get number of working days between two dates"""
        days = DateUtils.get_days_between(start_date, end_date) + 1
        weekends = 0
        
        current = start_date
        for _ in range(days):
            if DateUtils.is_weekend(current):
                weekends += 1
            current += timedelta(days=1)
        
        return days - weekends
    
    @staticmethod
    def get_financial_year(date_obj: date = None) -> Tuple[int, int]:
        """Get financial year (April-March) for a date"""
        if date_obj is None:
            date_obj = DateUtils.get_current_date()
        
        if date_obj.month >= 4:  # April or later
            return date_obj.year, date_obj.year + 1
        else:  # January-March
            return date_obj.year - 1, date_obj.year
    
    @staticmethod
    def get_academic_year(date_obj: date = None) -> Tuple[int, int]:
        """Get academic year (June-May) for a date"""
        if date_obj is None:
            date_obj = DateUtils.get_current_date()
        
        if date_obj.month >= 6:  # June or later
            return date_obj.year, date_obj.year + 1
        else:  # January-May
            return date_obj.year - 1, date_obj.year
    
    @staticmethod
    def get_age(date_of_birth: date) -> int:
        """Calculate age from date of birth"""
        today = DateUtils.get_current_date()
        age = today.year - date_of_birth.year
        
        # Check if birthday has occurred this year
        if (today.month, today.day) < (date_of_birth.month, date_of_birth.day):
            age -= 1
        
        return age
    
    @staticmethod
    def get_time_ago(dt: datetime) -> str:
        """Get human-readable time ago string"""
        now = DateUtils.get_current_datetime()
        diff = now - dt
        
        if diff.days > 365:
            years = diff.days // 365
            return f"{years} year{'s' if years > 1 else ''} ago"
        elif diff.days > 30:
            months = diff.days // 30
            return f"{months} month{'s' if months > 1 else ''} ago"
        elif diff.days > 0:
            return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
        else:
            return "just now"
    
    @staticmethod
    def get_next_month(date_obj: date) -> date:
        """Get same day next month"""
        if date_obj.month == 12:
            return date(date_obj.year + 1, 1, date_obj.day)
        else:
            return date(date_obj.year, date_obj.month + 1, date_obj.day)
    
    @staticmethod
    def get_previous_month(date_obj: date) -> date:
        """Get same day previous month"""
        if date_obj.month == 1:
            return date(date_obj.year - 1, 12, date_obj.day)
        else:
            return date(date_obj.year, date_obj.month - 1, date_obj.day)
    
    @staticmethod
    def get_quarter(date_obj: date) -> int:
        """Get quarter (1-4) for a date"""
        return (date_obj.month - 1) // 3 + 1
    
    @staticmethod
    def get_dates_in_quarter(year: int, quarter: int) -> Tuple[date, date]:
        """Get start and end dates for a quarter"""
        if quarter == 1:
            start = date(year, 1, 1)
            end = date(year, 3, 31)
        elif quarter == 2:
            start = date(year, 4, 1)
            end = date(year, 6, 30)
        elif quarter == 3:
            start = date(year, 7, 1)
            end = date(year, 9, 30)
        else:  # quarter == 4
            start = date(year, 10, 1)
            end = date(year, 12, 31)
        return start, end
    
    @staticmethod
    def is_leap_year(year: int) -> bool:
        """Check if year is a leap year"""
        return calendar.isleap(year)
    
    @staticmethod
    def get_days_in_month(year: int, month: int) -> int:
        """Get number of days in a month"""
        return calendar.monthrange(year, month)[1]
    
    @staticmethod
    def get_indian_festival_dates(year: int) -> List[Tuple[str, date]]:
        """Get major Indian festival dates (approximate)"""
        # Note: Actual dates vary based on lunar calendar
        # This is a simplified version
        festivals = [
            ("Republic Day", date(year, 1, 26)),
            ("Holi", date(year, 3, 8)),  # Approximate
            ("Independence Day", date(year, 8, 15)),
            ("Ganesh Chaturthi", date(year, 9, 2)),  # Approximate
            ("Dussehra", date(year, 10, 12)),  # Approximate
            ("Diwali", date(year, 11, 1)),  # Approximate
            ("Christmas", date(year, 12, 25)),
        ]
        return festivals
    
    @staticmethod
    def get_exam_season_dates(year: int, semester: int = 1) -> Tuple[date, date]:
        """Get typical exam season dates for Indian universities"""
        if semester == 1:  # Odd semester (Nov-Dec)
            start = date(year, 11, 15)
            end = date(year, 12, 31)
        else:  # Even semester (Apr-May)
            start = date(year, 4, 15)
            end = date(year, 5, 31)
        return start, end


# Singleton instance
date_utils = DateUtils()