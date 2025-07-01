"""
Модели данных для Yandex Tracker
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Issue:
    """Модель задачи в Yandex Tracker"""
    id: str
    key: str
    summary: str
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    assignee: Optional[str] = None
    queue: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    deadline: Optional[datetime] = None
    tags: Optional[List[str]] = None
    type: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Issue':
        """Создать Issue из словаря API"""
        return cls(
            id=data.get('id'),
            key=data.get('key'),
            summary=data.get('summary', ''),
            description=data.get('description'),
            status=data.get('status', {}).get('display') if data.get('status') else None,
            priority=data.get('priority', {}).get('display') if data.get('priority') else None,
            assignee=data.get('assignee', {}).get('display') if data.get('assignee') else None,
            queue=data.get('queue', {}).get('key') if data.get('queue') else None,
            created_at=datetime.fromisoformat(data['createdAt'].replace('Z', '+00:00')) if data.get('createdAt') else None,
            updated_at=datetime.fromisoformat(data['updatedAt'].replace('Z', '+00:00')) if data.get('updatedAt') else None,
            deadline=datetime.fromisoformat(data['deadline'].replace('Z', '+00:00')) if data.get('deadline') else None,
            tags=[tag['name'] for tag in data.get('tags', [])] if data.get('tags') else None,
            type=data.get('type', {}).get('display') if data.get('type') else None
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразовать в словарь для API"""
        result = {
            'summary': self.summary,
            'description': self.description
        }
        
        if self.queue:
            result['queue'] = self.queue
        if self.priority:
            result['priority'] = self.priority
        if self.assignee:
            result['assignee'] = self.assignee
        if self.deadline:
            result['deadline'] = self.deadline.isoformat()
        if self.tags:
            result['tags'] = self.tags
        if self.type:
            result['type'] = self.type
            
        return result


@dataclass
class Queue:
    """Модель очереди в Yandex Tracker"""
    key: str
    name: str
    description: Optional[str] = None
    lead: Optional[str] = None
    issue_types: Optional[List[str]] = None
    priorities: Optional[List[str]] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Queue':
        """Создать Queue из словаря API"""
        return cls(
            key=data.get('key'),
            name=data.get('name', ''),
            description=data.get('description'),
            lead=data.get('lead', {}).get('display') if data.get('lead') else None,
            issue_types=[t['display'] for t in data.get('issueTypes', [])] if data.get('issueTypes') else None,
            priorities=[p['display'] for p in data.get('priorities', [])] if data.get('priorities') else None
        )


@dataclass
class User:
    """Модель пользователя в Yandex Tracker"""
    id: str
    name: str
    email: Optional[str] = None
    login: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'User':
        """Создать User из словаря API"""
        return cls(
            id=data.get('id'),
            name=data.get('display', ''),
            email=data.get('email'),
            login=data.get('login')
        )


@dataclass
class QueueSummary:
    """Модель дайджеста очереди"""
    queue_name: str
    total_issues: int
    in_progress: int
    completed: int
    overdue: int
    recent_issues: List[Issue]
    priority_stats: Dict[str, int]
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразовать в словарь для промтов"""
        return {
            'name': self.queue_name,
            'total_issues': self.total_issues,
            'in_progress': self.in_progress,
            'completed': self.completed,
            'overdue': self.overdue,
            'recent_issues': [
                {
                    'summary': issue.summary,
                    'status': issue.status or 'Неизвестно'
                }
                for issue in self.recent_issues
            ],
            'priority_stats': self.priority_stats
        } 