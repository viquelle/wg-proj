import enum

from sqlalchemy.inspection import inspect

def orn_to_dict(obj, include_relationships=False) -> dict | None:
    """
    Превращает ORM объект в словарь
    :param obj: сам объект
    :param include_relationships: включать ли зависимости
    :return: dict
    """
    if obj is None:
        return None
    
    data = {}
    mapper = inspect(obj) ## Позволяет получить данные объекта из SQLAlchemy
    
    for column in mapper.mapper.column_attrs:
        val = getattr(obj, column.key)
        data[column.key] = val.value if isinstance(val, enum.Enum) else val
    
    if include_relationships:
        for name, relation in mapper.mapper.relationships.items():
            value = getattr(obj, name)
            
            if value is None:
                data[name] = None
            elif relation.uselist:
                data[name] = [orn_to_dict(x, include_relationships=False) for x in value]
            else:
                data[name] = orn_to_dict(value, include_relationships=False)
    return data
    