#!/usr/bin/env python3
import os
import json
import uvicorn
from typing import Optional, Dict, Any
from fastapi import FastAPI, HTTPException, Depends, Query, Header, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from gitlab_commits import get_commits_data

# 初始化FastAPI应用
app = FastAPI(
    title="GitLab Commits API",
    description="获取GitLab提交记录",
    version="1.0.0",
)

# 请求模型
class GitLabCommitRequest(BaseModel):
    gitlab_url: str = Field(..., description="GitLab实例URL")
    admin_token: str = Field(..., description="GitLab管理员Token")
    days: int = Field(1, description="要获取的过去天数（默认：1，表示今天）")
    debug: bool = Field(False, description="开启调试模式（默认：False）")
    threads: int = Field(0, description="使用的线程数量（默认：0，表示自动设置）")

# 响应模型
class GitLabCommitResponse(BaseModel):
    metadata: Dict[str, Any]
    commits: list

# API路由
@app.post("/api/commits", response_model=GitLabCommitResponse, summary="获取GitLab提交记录")
async def get_commits(request: GitLabCommitRequest):
    """
    获取GitLab提交记录
    
    - **gitlab_url**: GitLab实例的URL（必填）
    - **admin_token**: GitLab管理员账号的私人访问令牌（必填）
    - **days**: 要获取的过去天数（默认：1，表示今天）
    - **debug**: 开启调试模式（默认：False）
    - **threads**: 线程数量（默认：0，表示自动设置）
    
    返回包含提交记录的JSON对象
    """
    try:
        # 调用现有函数获取提交数据
        result = get_commits_data(
            gitlab_url=request.gitlab_url,
            admin_token=request.admin_token,
            days=request.days,
            debug=request.debug,
            threads=request.threads
        )
        
        # 检查是否有错误
        if 'error' in result.get('metadata', {}):
            raise HTTPException(status_code=500, detail=result['metadata']['error'])
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 简化版GET接口（需要通过请求头提供token）
@app.get("/api/commits", response_model=GitLabCommitResponse, summary="获取GitLab提交记录（GET方法）")
async def get_commits_by_get(
    gitlab_url: str = Query(..., description="GitLab实例URL"),
    days: int = Query(1, description="要获取的过去天数"),
    debug: bool = Query(False, description="开启调试模式"),
    threads: int = Query(0, description="使用的线程数量"),
    x_gitlab_token: str = Header(..., description="GitLab管理员Token", alias="X-GitLab-Token")
):
    """
    使用GET方法获取GitLab提交记录
    
    - **gitlab_url**: GitLab实例的URL（必填，查询参数）
    - **days**: 要获取的过去天数（默认：1，表示今天）
    - **debug**: 开启调试模式（默认：False）
    - **threads**: 线程数量（默认：0，表示自动设置）
    - **X-GitLab-Token**: GitLab管理员账号的私人访问令牌（必填，请求头）
    
    返回包含提交记录的JSON对象
    """
    try:
        # 调用现有函数获取提交数据
        result = get_commits_data(
            gitlab_url=gitlab_url,
            admin_token=x_gitlab_token,
            days=days,
            debug=debug,
            threads=threads
        )
        
        # 检查是否有错误
        if 'error' in result.get('metadata', {}):
            raise HTTPException(status_code=500, detail=result['metadata']['error'])
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 运行时信息
@app.get("/", summary="API服务信息")
async def read_root():
    """获取API服务基本信息"""
    return {
        "name": "GitLab Commits API",
        "version": "1.0.0",
        "description": "用于获取GitLab提交记录的API服务",
        "endpoints": [
            {
                "path": "/api/commits",
                "methods": ["GET", "POST"],
                "description": "获取GitLab提交记录"
            },
            {
                "path": "/docs",
                "methods": ["GET"],
                "description": "API文档"
            }
        ]
    }

# 主函数
def main():
    # 从环境变量获取配置
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    
    # 启动服务
    uvicorn.run(app, host=host, port=port)

if __name__ == "__main__":
    main() 