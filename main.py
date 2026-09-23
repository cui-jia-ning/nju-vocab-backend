from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from passlib.context import CryptContext
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, date
from typing import List

from config import settings
from database import engine, get_db, Base
from models import User, Word, WordProgress, LoginLog
from schemas import (
    UserCreate, UserLogin, UserResponse, Token,
    WordCreate, WordResponse, ReviewItem, StatsResponse,
)

Base.metadata.create_all(bind=engine)

app = FastAPI(title="NJU Vocab Filter Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

EBBINGHAUS_INTERVALS = [1, 2, 4, 7, 15, 30]


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def create_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        user_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="无效凭证")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    return user


@app.post("/register", response_model=UserResponse)
def register(data: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == data.username).first():
        raise HTTPException(status_code=400, detail="用户名已存在")
    user = User(username=data.username, password_hash=hash_password(data.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.post("/login", response_model=Token)
def login(data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == data.username).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    now = datetime.utcnow()
    user.last_login = now
    user.last_login_date = now.date()

    log = LoginLog(user_id=user.id, login_at=now, login_date=now.date())
    db.add(log)
    db.commit()

    return {"access_token": create_token({"sub": str(user.id)}), "token_type": "bearer"}


@app.get("/me", response_model=UserResponse)
def get_me(user: User = Depends(get_current_user)):
    return user


@app.post("/words", response_model=WordResponse)
def add_word(data: WordCreate, db: Session = Depends(get_db)):
    if db.query(Word).filter(Word.word == data.word).first():
        raise HTTPException(status_code=400, detail="单词已存在")
    word = Word(word=data.word, meaning=data.meaning)
    db.add(word)
    db.commit()
    db.refresh(word)
    return word


@app.get("/words", response_model=List[WordResponse])
def list_words(db: Session = Depends(get_db)):
    return db.query(Word).all()


@app.get("/review/today", response_model=List[ReviewItem])
def get_today_review(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    today = date.today()
    progress_list = (
        db.query(WordProgress)
        .filter(
            WordProgress.user_id == user.id,
            WordProgress.mastered == False,
            WordProgress.next_review_date <= today,
        )
        .all()
    )
    result = []
    for p in progress_list:
        word = db.query(Word).filter(Word.id == p.word_id).first()
        if word:
            result.append(
                ReviewItem(
                    word_id=word.id,
                    word=word.word,
                    meaning=word.meaning,
                    review_count=p.review_count,
                    next_review_date=p.next_review_date,
                )
            )
    return result


@app.post("/review/{word_id}")
def submit_review(word_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    word = db.query(Word).filter(Word.id == word_id).first()
    if not word:
        raise HTTPException(status_code=404, detail="单词不存在")

    progress = (
        db.query(WordProgress)
        .filter(WordProgress.user_id == user.id, WordProgress.word_id == word_id)
        .first()
    )

    if not progress:
        progress = WordProgress(
            user_id=user.id, word_id=word_id, review_count=0, next_review_date=date.today()
        )
        db.add(progress)

    progress.review_count += 1
    progress.last_reviewed_at = datetime.utcnow()

    idx = min(progress.review_count - 1, len(EBBINGHAUS_INTERVALS) - 1)
    progress.next_review_date = date.today() + timedelta(days=EBBINGHAUS_INTERVALS[idx])

    if progress.review_count >= len(EBBINGHAUS_INTERVALS):
        progress.mastered = True

    db.commit()
    return {"status": "ok", "next_review": progress.next_review_date.isoformat()}


@app.get("/stats", response_model=StatsResponse)
def get_stats(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="仅管理员可访问")

    today = date.today()

    total_users = db.query(User).count()
    total_logins_today = db.query(LoginLog).filter(LoginLog.login_date == today).count()
    unique_logins_today = (
        db.query(LoginLog.user_id).filter(LoginLog.login_date == today).distinct().count()
    )
    total_words = db.query(Word).count()
    total_reviews_today = (
        db.query(WordProgress)
        .filter(WordProgress.last_reviewed_at >= datetime.combine(today, datetime.min.time()))
        .count()
    )
    words_due_today = (
        db.query(WordProgress)
        .filter(WordProgress.next_review_date <= today, WordProgress.mastered == False)
        .count()
    )

    return StatsResponse(
        total_users=total_users,
        total_logins_today=total_logins_today,
        unique_logins_today=unique_logins_today,
        total_words=total_words,
        total_reviews_today=total_reviews_today,
        words_due_today=words_due_today,
    )


@app.get("/health")
def health_check():
    return {"status": "ok"}


app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def root():
    return FileResponse("static/index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
