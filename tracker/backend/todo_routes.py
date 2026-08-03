"""FastAPI routes for TODO / notification management."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from models import (
    Todo,
    TodoCreate,
    TodoAutoCreate,
    TodoUpdate,
    TodoResponse,
    TodoCountResponse,
    TodoStatus,
)

router = APIRouter(prefix="/api/todos", tags=["todos"])


@router.get("", response_model=list[TodoResponse])
def list_todos(
    status: Optional[TodoStatus] = Query(None, description="Filter by status"),
    category: Optional[str] = Query(None, description="Filter by category"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List all todos with optional filtering by status and category."""
    query = db.query(Todo)
    if status is not None:
        query = query.filter(Todo.status == status)
    if category is not None:
        query = query.filter(Todo.category == category)
    query = query.order_by(Todo.created_at.desc())
    todos = query.offset(offset).limit(limit).all()
    return todos


@router.get("/pending/count", response_model=TodoCountResponse)
def pending_count(db: Session = Depends(get_db)):
    """Get the count of pending todos (for badge display)."""
    count = db.query(Todo).filter(Todo.status == TodoStatus.pending).count()
    return TodoCountResponse(pending_count=count)


@router.post("", response_model=TodoResponse, status_code=201)
def create_todo(payload: TodoCreate, db: Session = Depends(get_db)):
    """Create a new todo manually."""
    todo = Todo(
        title=payload.title,
        description=payload.description,
        category=payload.category,
        priority=payload.priority,
        job_id=payload.job_id,
        job_title=payload.job_title,
        company=payload.company,
        action_url=payload.action_url,
        reminder_at=payload.reminder_at,
        metadata_json=payload.metadata_json,
    )
    db.add(todo)
    db.commit()
    db.refresh(todo)
    return todo


@router.patch("/{todo_id}", response_model=TodoResponse)
def update_todo(todo_id: str, payload: TodoUpdate, db: Session = Depends(get_db)):
    """Update a todo (mark done/dismissed, edit title, etc)."""
    todo = db.query(Todo).filter(Todo.id == todo_id).first()
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")

    if payload.status is not None:
        todo.status = payload.status
        if payload.status in (TodoStatus.done, TodoStatus.dismissed):
            todo.completed_at = datetime.utcnow()
        elif payload.status == TodoStatus.pending:
            todo.completed_at = None
    if payload.title is not None:
        todo.title = payload.title
    if payload.description is not None:
        todo.description = payload.description
    if payload.priority is not None:
        todo.priority = payload.priority
    if payload.reminder_at is not None:
        todo.reminder_at = payload.reminder_at

    db.commit()
    db.refresh(todo)
    return todo


@router.delete("/{todo_id}", status_code=204)
def delete_todo(todo_id: str, db: Session = Depends(get_db)):
    """Delete a todo permanently."""
    todo = db.query(Todo).filter(Todo.id == todo_id).first()
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")
    db.delete(todo)
    db.commit()
    return None


@router.post("/auto", response_model=TodoResponse, status_code=201)
def auto_create_todo(payload: TodoAutoCreate, db: Session = Depends(get_db)):
    """Internal endpoint for the agent to create todos automatically."""
    todo = Todo(
        title=payload.title,
        description=payload.description,
        category=payload.category,
        priority=payload.priority,
        job_id=payload.job_id,
        job_title=payload.job_title,
        company=payload.company,
        action_url=payload.action_url,
        reminder_at=payload.reminder_at,
        metadata_json=payload.metadata_json,
    )
    db.add(todo)
    db.commit()
    db.refresh(todo)
    return todo
