# (定義 API 的資料模型)
# app/models.py
from pydantic import BaseModel, Field
from typing import Optional, List

class SearchFilters(BaseModel):
    genre: Optional[str] = Field(None, description="要篩選的電影類型，例如 'Action' 或 'Comedy'")
    min_year: Optional[int] = Field(None, description="篩選上映年份大於等於此年份的電影")
    min_rating: Optional[float] = Field(None, description="篩選評分大於等於此分數的電影")

class SearchRequest(BaseModel):
    query: str = Field(description="使用者的自然語言查詢，例如 'a movie about space travel and AI'")
    filters: Optional[SearchFilters] = None
    top_k: int = 10

class Movie(BaseModel):
    id: int
    title: str
    overview: Optional[str]
    genres: Optional[List[str]]
    release_year: Optional[int]
    vote_average: Optional[float]

    class Config:
        from_attributes = True # Pydantic v2 的 orm_mode

class SearchResponse(BaseModel):
    count: int
    results: List[Movie]

# app/models.py (在檔案最末端加上這段)

class AskRequest(BaseModel):
    question: str = Field(description="使用者針對單一電影提出的問題")

class AskResponse(BaseModel):
    movie_id: int
    question: str
    answer: str