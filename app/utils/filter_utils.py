
from datetime import datetime
from enum import Enum # Import Enum for type checking

class FilterUtils:

    @staticmethod
    def _matches_keyword(item, keyword, attributes):
        """检查对象的指定属性是否包含关键词（不区分大小写）"""
        if not keyword:
            return True
        keyword_lower = keyword.lower()
        for attr in attributes:
            value = getattr(item, attr, None)
            if value and isinstance(value, str) and keyword_lower in value.lower():
                return True
        return False

    @staticmethod
    def _matches_enum(item, enum_value, attribute):
        """检查对象的枚举属性是否匹配"""
        if enum_value is None or enum_value.startswith("全部"):
             return True
        item_value = getattr(item, attribute, None)
        if isinstance(item_value, Enum):
             return item_value.value == enum_value
        return str(item_value) == enum_value


    @staticmethod
    def _matches_date_range(item, start_date, end_date, attribute):
        """检查对象的日期属性是否在范围内"""
        item_date = getattr(item, attribute, None)
        if not item_date: return False # Treat missing date as not matching

        if isinstance(item_date, datetime):
            item_date = item_date.date()
        if isinstance(start_date, datetime): start_date = start_date.date()
        if isinstance(end_date, datetime): end_date = end_date.date()


        match_start = start_date is None or item_date >= start_date
        match_end = end_date is None or item_date <= end_date
        return match_start and match_end

    @staticmethod
    def _matches_amount_range(item, min_amount, max_amount, attribute):
        """检查对象的金额属性是否在范围内"""
        item_amount = getattr(item, attribute, None)
        if item_amount is None: return False # Treat missing amount as not matching

        match_min = min_amount is None or item_amount >= min_amount
        match_max = max_amount is None or item_amount <= max_amount
        return match_min and match_max

    @staticmethod
    def apply_filters(data_list, filter_criteria, attribute_mapping=None):
        """
        根据筛选标准过滤对象列表。

        Args:
            data_list: 包含对象的列表。
            filter_criteria: 包含筛选条件的字典，例如：
                {
                    'keyword': 'search term',
                    'keyword_attributes': ['name', 'description'], # 要搜索关键词的属性列表
                    'category': '费用类别值', # 或 'doc_type', 'outcome_type', 'status' 等
                    'start_date': date(2023, 1, 1),
                    'end_date': date(2023, 12, 31),
                    'min_amount': 100.0,
                    'max_amount': 500.0,
                    'status': '已发布'
                }
            attribute_mapping: (可选) 字典，将 filter_criteria 中的键映射到对象上的实际属性名。
                               例如: {'category': 'category_enum_attr', 'status': 'outcome_status'}
                               如果为 None，则假定 filter_criteria 中的键直接对应属性名。
                               'keyword' 的映射通常为 None，因为它由 'keyword_attributes' 处理。

        Returns:
            过滤后的对象列表。
        """
        if attribute_mapping is None:
            attribute_mapping = {}

        filtered_list = []
        keyword = filter_criteria.get('keyword')
        keyword_attributes = filter_criteria.get('keyword_attributes', [])

        for item in data_list:
            match = True

            if keyword and keyword_attributes:
                 mapped_keyword_attributes = [attribute_mapping.get(attr, attr) for attr in keyword_attributes]
                 if not FilterUtils._matches_keyword(item, keyword, mapped_keyword_attributes):
                     continue # Skip to next item if keyword doesn't match

            for key, filter_value in filter_criteria.items():
                if key in ['keyword', 'keyword_attributes']: continue # Already handled

                attr_name = attribute_mapping.get(key, key)

                if key == 'start_date':
                    start_date = filter_criteria.get('start_date')
                    end_date = filter_criteria.get('end_date')
                    date_attr = attribute_mapping.get('date', 'date') # Default to 'date' if not mapped
                    if not FilterUtils._matches_date_range(item, start_date, end_date, date_attr):
                        match = False; break
                elif key == 'end_date':
                    continue # Handled by start_date check

                elif key == 'min_amount':
                     min_amount = filter_criteria.get('min_amount')
                     max_amount = filter_criteria.get('max_amount')
                     amount_attr = attribute_mapping.get('amount', 'amount') # Default to 'amount'
                     if not FilterUtils._matches_amount_range(item, min_amount, max_amount, amount_attr):
                          match = False; break
                elif key == 'max_amount':
                     continue # Handled by min_amount check

                elif key in ['category', 'doc_type', 'outcome_type', 'status']: # Enum/Type checks
                    if not FilterUtils._matches_enum(item, filter_value, attr_name):
                         match = False; break


            if match:
                filtered_list.append(item)

        return filtered_list