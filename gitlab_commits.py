#!/usr/bin/env python3
import os
import json
import datetime
import gitlab
from typing import Dict, List, Any, Optional, Tuple, Union
import argparse
import sys
import concurrent.futures
from tqdm import tqdm

def parse_args():
    parser = argparse.ArgumentParser(description='Fetch GitLab commits from all users and projects for the current day')
    parser.add_argument('--url', type=str, required=True, help='GitLab URL (e.g., https://gitlab.com)')
    parser.add_argument('--admin-token', type=str, required=True, help='GitLab admin private token')
    parser.add_argument('--output', type=str, default='gitlab_commits.txt', help='Output TXT file path')
    parser.add_argument('--days', type=int, default=1, help='Number of days to look back (default: 1)')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode for verbose output')
    parser.add_argument('--threads', type=int, default=0, help='Number of threads to use (default: CPU count * 4)')
    parser.add_argument('--format', type=str, choices=['txt', 'json'], default='txt', help='Output format (txt or json)')
    return parser.parse_args()

def get_gitlab_client(url: str, token: str, debug: bool) -> gitlab.Gitlab:
    """Create and return an authenticated GitLab client using admin token."""
    try:
        if debug:
            print(f"Attempting to connect to GitLab at {url} with provided token")
        
        gl = gitlab.Gitlab(url=url, private_token=token)
        gl.auth()
        
        # Verify we have admin access
        current_user = gl.user
        if debug:
            print(f"Successfully authenticated as user: {current_user.username}")
        
        if not hasattr(current_user, 'is_admin') or not current_user.is_admin:
            print("Warning: The provided token does not belong to an admin user or admin status cannot be determined.")
            print("Some data might not be accessible.")
        else:
            if debug:
                print("Confirmed admin access.")
        
        return gl
    except Exception as e:
        print(f"Error authenticating with GitLab: {e}")
        print("Please check your URL and admin token.")
        raise

def get_all_projects(gl: gitlab.Gitlab, debug: bool) -> List[Dict[str, Any]]:
    """Get all projects visible to admin."""
    projects_list = []
    try:
        if debug:
            print("Attempting to retrieve all projects...")
        
        try:
            projects = gl.projects.list(all=True, visibility='all')
            if debug:
                print(f"Retrieved {len(projects)} projects using visibility='all' parameter")
        except Exception as e:
            if debug:
                print(f"Error using visibility parameter: {e}")
            # Fallback to simpler query
            projects = gl.projects.list(all=True)
            if debug:
                print(f"Retrieved {len(projects)} projects without visibility parameter")
        
        if not projects:
            print("No projects found with first attempt, trying with manual pagination...")
            projects = []
            page = 1
            while True:
                batch = gl.projects.list(page=page, per_page=100)
                if not batch:
                    break
                projects.extend(batch)
                print(f"Retrieved page {page} with {len(batch)} projects")
                page += 1
                if page > 100:  # Safety limit
                    print("Warning: Too many pages, stopping at 100 pages")
                    break
        
        projects_list = [
            {
                'id': project.id,
                'name': project.name,
                'path_with_namespace': project.path_with_namespace,
                'visibility': getattr(project, 'visibility', 'unknown'),
                'web_url': project.web_url
            }
            for project in projects
        ]
        
        if debug:
            print(f"Successfully processed {len(projects_list)} projects")
            
        return projects_list
    except Exception as e:
        print(f"Error retrieving projects: {e}")
        return projects_list

def get_project_commits(project_info: Dict[str, Any], gl: gitlab.Gitlab, start_date: datetime.datetime, 
                        end_date: datetime.datetime, debug: bool = False) -> List[Dict[str, Any]]:
    """Get commits for a single project within the date range."""
    project_commits = []
    try:
        project_id = project_info['id']
        project_path = project_info['path_with_namespace']
        
        if debug:
            print(f"Processing project: {project_path}")
        
        project = gl.projects.get(project_id)
        since_str = start_date.isoformat()
        until_str = end_date.isoformat()
        
        # Get commits since the start date
        try:
            # Try with both since and until dates
            commits = project.commits.list(all=True, since=since_str, until=until_str)
            if debug:
                print(f"  Found {len(commits)} commits for {project_path}")
        except Exception as e:
            if debug:
                print(f"  Error retrieving commits with date range: {e}")
            try:
                commits = project.commits.list(all=True, since=since_str)
                if debug:
                    print(f"  Found {len(commits)} commits with 'since' only")
            except Exception as inner_e:
                if debug:
                    print(f"  Error retrieving commits with 'since' only: {inner_e}")
                commits = []
                try:
                    page = 1
                    while True:
                        batch = project.commits.list(page=page, per_page=100)
                        if not batch:
                            break
                        for commit in batch:
                            if hasattr(commit, 'created_at'):
                                commit_date = datetime.datetime.fromisoformat(commit.created_at.replace('Z', '+00:00'))
                                if start_date <= commit_date <= end_date:
                                    commits.append(commit)
                        page += 1
                        if page > 10:  # Limit to avoid too many API calls
                            break
                    if debug:
                        print(f"  Found {len(commits)} commits with manual filtering")
                except Exception as final_e:
                    if debug:
                        print(f"  Failed all commit retrieval methods: {final_e}")
        
        for commit in commits:
            try:
                # Get full commit data
                full_commit = project.commits.get(commit.id)
                
                try:
                    # Get commit diff (this may fail for some commits)
                    raw_diff = full_commit.diff(get_all=True)
                    # Filter the diff to keep only the required fields
                    diff = filter_diff_data(raw_diff)
                except Exception as diff_e:
                    if debug:
                        print(f"  Error retrieving diff for commit {commit.id}: {diff_e}")
                    diff = []
                
                # Convert created_at to datetime if it's a string
                created_at = commit.created_at
                if isinstance(created_at, str):
                    try:
                        # Handle ISO format with timezone
                        created_at = created_at.replace('Z', '+00:00')
                        dt = datetime.datetime.fromisoformat(created_at)
                        created_at = dt.isoformat()
                    except Exception:
                        # Keep as string if parsing fails
                        pass
                
                commit_data = {
                    'title': commit.title,
                    'message': commit.message,
                    'author_name': commit.author_name,
                    'author_email': commit.author_email,
                    'created_at': created_at,
                    'project_path': project_info['path_with_namespace'],
                    'diff': diff,
                }
                project_commits.append(commit_data)
                if debug:
                    print(f"  Processed commit {commit.short_id}: {commit.title}")
            except Exception as e:
                print(f"  Error retrieving commit details for {commit.id} in project {project_id}: {e}")
                continue
            
    except Exception as e:
        if debug:
            print(f"Error retrieving commits for project {project_info.get('id', 'unknown')}: {e}")
    
    return project_commits

def get_today_commits(gl: gitlab.Gitlab, projects: List[Dict[str, Any]], days: int = 1, debug: bool = False, threads: int = 0) -> List[Dict[str, Any]]:
    """Get all commits from today for all projects using admin privileges with multithreading."""
    # Calculate the date range
    end_date = datetime.datetime.now()
    start_date = end_date.replace(hour=0, minute=0, second=0, microsecond=0) - datetime.timedelta(days=days-1)
    
    print(f"Retrieving commits between {start_date.isoformat()} and {end_date.isoformat()}")
    
    all_commits = []
    total_projects = len(projects)
    
    # Use ThreadPoolExecutor for parallel processing
    if threads <= 0:
        max_workers = min(32, os.cpu_count() * 4)  # Default: CPU count * 4, max 32
    else:
        max_workers = threads
    
    print(f"Using {max_workers} threads to process {total_projects} projects")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Create a dictionary of future to project name for better progress tracking
        future_to_project = {
            executor.submit(get_project_commits, project, gl, start_date, end_date, debug): 
            project['path_with_namespace'] 
            for project in projects
        }
        
        # Create a progress bar to track completion
        processed_commits = 0
        with tqdm(total=total_projects, desc="Fetching projects", disable=debug) as progress:
            # Process results as they complete
            for future in concurrent.futures.as_completed(future_to_project):
                project_path = future_to_project[future]
                try:
                    project_commits = future.result()
                    all_commits.extend(project_commits)
                    processed_commits += len(project_commits)
                    progress.set_postfix(commits=processed_commits)
                    if debug:
                        print(f"Completed {project_path}: {len(project_commits)} commits")
                except Exception as e:
                    print(f"Error processing {project_path}: {e}")
                
                # Update progress bar
                progress.update(1)
    
    print(f"Total commits retrieved: {len(all_commits)}")
    return all_commits

def filter_diff_data(diff: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filter diff data to only keep required fields."""
    filtered_diff = []
    for diff_item in diff:
        filtered_item = {
            'new_path': diff_item.get('new_path', ''),
            'old_path': diff_item.get('old_path', '')
        }
        # Only include new_file if it exists
        if 'new_file' in diff_item:
            filtered_item['new_file'] = diff_item['new_file']
            
        filtered_diff.append(filtered_item)
    return filtered_diff

def get_user_batch(gl: gitlab.Gitlab, page: int, per_page: int = 100, debug: bool = False) -> List[Dict[str, Any]]:
    """Get a batch of users for parallel processing."""
    try:
        batch = gl.users.list(page=page, per_page=per_page)
        if debug:
            print(f"Retrieved user batch page {page} with {len(batch)} users")
        
        return [
            {
                'id': user.id,
                'username': user.username,
                'name': user.name,
                'email': getattr(user, 'email', None),
                'state': getattr(user, 'state', 'unknown')
            }
            for user in batch
        ]
    except Exception as e:
        if debug:
            print(f"Error retrieving user batch on page {page}: {e}")
        return []

def get_all_users(gl: gitlab.Gitlab, debug: bool, threads: int = 0) -> List[Dict[str, Any]]:
    """Get all users using admin privileges with multithreading."""
    try:
        if debug:
            print("Attempting to retrieve all users...")
        
        # First try standard call to get total count
        try:
            # Try to get first page to see total count
            first_page = gl.users.list(page=1, per_page=20)
            if hasattr(first_page, 'total'):
                total_pages = (first_page.total + 99) // 100  # Ceiling division for pages needed
            else:
                # If we can't get total, try a reasonable number of pages
                total_pages = 20
                
            if debug:
                print(f"Estimated {total_pages} pages of users needed")
                
            # Determine max workers
            if threads <= 0:
                max_workers = min(16, os.cpu_count() * 2)  # Users fetch typically needs fewer threads
            else:
                max_workers = threads
                
            all_users = []
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit tasks for each page
                futures = [executor.submit(get_user_batch, gl, page, 100, debug) 
                          for page in range(1, total_pages + 1)]
                
                # Process results with progress bar
                with tqdm(total=len(futures), desc="Fetching users", disable=debug) as progress:
                    for future in concurrent.futures.as_completed(futures):
                        try:
                            batch_users = future.result()
                            all_users.extend(batch_users)
                            progress.update(1)
                            progress.set_postfix(total=len(all_users))
                        except Exception as e:
                            print(f"Error processing user batch: {e}")
                            progress.update(1)
            
            if len(all_users) == 0:
                # Fallback to old method if parallel fetch fails
                if debug:
                    print("Parallel retrieval failed, falling back to sequential method")
                return _get_all_users_sequential(gl, debug)
                
            return all_users
                
        except Exception as e:
            if debug:
                print(f"Error with parallel user retrieval: {e}")
            # Fallback to sequential method
            return _get_all_users_sequential(gl, debug)
            
    except Exception as e:
        print(f"Error retrieving users: {e}")
        return []

def _get_all_users_sequential(gl: gitlab.Gitlab, debug: bool) -> List[Dict[str, Any]]:
    """Legacy sequential method to get all users as fallback."""
    try:
        # Try standard call first
        try:
            users = gl.users.list(all=True)
            if debug:
                print(f"Retrieved {len(users)} users with standard call")
        except Exception as e:
            if debug:
                print(f"Standard user retrieval failed: {e}")
            # Fallback to pagination
            users = []
            page = 1
            while True:
                try:
                    batch = gl.users.list(page=page, per_page=100)
                    if not batch:
                        break
                    users.extend(batch)
                    print(f"Retrieved page {page} with {len(batch)} users")
                    page += 1
                    if page > 50:  # Safety limit
                        break
                except Exception as inner_e:
                    print(f"Error on page {page}: {inner_e}")
                    break
        
        return [
            {
                'id': user.id,
                'username': user.username,
                'name': user.name,
                'email': getattr(user, 'email', None),
                'state': getattr(user, 'state', 'unknown')
            }
            for user in users
        ]
    except Exception as e:
        print(f"Error in sequential user retrieval: {e}")
        return []

def save_to_txt(data: Dict[str, Any], output_file: str):
    """Save data to a TXT file in a readable format."""
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            # Write metadata section
            f.write("=== GITLAB COMMITS REPORT ===\n")
            f.write(f"Generated: {data['metadata']['date']}\n")
            f.write(f"GitLab URL: {data['metadata']['gitlab_url']}\n")
            f.write(f"Days included: {data['metadata']['days_included']}\n")
            f.write(f"Projects count: {data['metadata']['projects_count']}\n")
            f.write(f"Users count: {data['metadata']['users_count']}\n")
            f.write(f"Commits count: {data['metadata']['commits_count']}\n")
            
            # Write commits section
            f.write("=== COMMITS ===\n")
            
            if not data['commits']:
                f.write("No commits found in the specified time range.\n")
            else:
                for i, commit in enumerate(data['commits'], 1):
                    f.write(f"Commit #{i}\n")
                    f.write(f"Project: {commit['project_path']}\n")
                    f.write(f"Title: {commit['title']}\n")
                    f.write(f"Author: {commit['author_name']} <{commit['author_email']}>\n")
                    f.write(f"Date: {commit['created_at']}\n")
                    f.write(f"Message:{commit['message']}\n")
                    
                    # Write diff information
                    if commit['diff']:
                        f.write("Changes:\n")
                        for diff_item in commit['diff']:
                            if diff_item.get('new_file', False):
                                f.write(f"  New file: {diff_item['new_path']}\n")
                            else:
                                f.write(f"  Modified: {diff_item['new_path']}\n")
                                if diff_item.get('old_path') and diff_item['old_path'] != diff_item['new_path']:
                                    f.write(f"    (renamed from: {diff_item['old_path']})\n")
                    else:
                        f.write("No diff information available.\n")
                    
                    f.write("\n" + "-" * 3 + "\n\n")
        
        print(f"Data successfully saved to {output_file}")
    except Exception as e:
        print(f"Error saving data to {output_file}: {e}")
        raise

def save_to_json(data: Dict[str, Any], output_file: str):
    """Save data to a JSON file."""
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Data successfully saved to {output_file}")
    except Exception as e:
        print(f"Error saving data to {output_file}: {e}")
        raise

def get_commits_data(gitlab_url: str, admin_token: str, days: int = 1, debug: bool = False, threads: int = 0) -> Dict[str, Any]:
    """
    Main function to get commits data, extracted from main() for reuse by API.
    
    Args:
        gitlab_url: GitLab instance URL
        admin_token: GitLab admin token
        days: Number of days to look back
        debug: Enable debug output
        threads: Number of threads to use
    
    Returns:
        Dict with metadata and commits data
    """
    try:
        if debug:
            print(f"Connecting to GitLab at {gitlab_url} with admin privileges...")
        gl = get_gitlab_client(gitlab_url, admin_token, debug)
        
        if debug:
            print("Fetching all projects...")
        projects = get_all_projects(gl, debug)
        if debug:
            print(f"Found {len(projects)} projects")
        
        if debug:
            print("Fetching all users (in parallel)...")
        users = get_all_users(gl, debug, threads)
        if debug:
            print(f"Found {len(users)} users")
        
        if debug:
            print(f"Fetching commits from the last {days} day(s) with multithreading...")
        commits = get_today_commits(gl, projects, days, debug, threads)
        if debug:
            print(f"Found {len(commits)} commits")
        
        # Prepare data for output file
        data = {
            'metadata': {
                'date': datetime.datetime.now().isoformat(),
                'gitlab_url': gitlab_url,
                'days_included': days,
                'projects_count': len(projects),
                'users_count': len(users),
                'commits_count': len(commits)
            },
            'commits': commits
        }
        
        if len(commits) == 0 and debug:
            print("\nWARNING: No commits were found!")
            print("Possible reasons:")
            print("1. No commits were made today or in the specified time range")
            print("2. Token permissions issue - make sure your token has sufficient permissions")
            print("3. API limitations - some GitLab instances have restricted APIs")
        
        return data
    except Exception as e:
        error_msg = f"ERROR: An unexpected error occurred: {e}"
        print(error_msg)
        if debug:
            import traceback
            traceback.print_exc()
        # For API usage, we'll return an error structure
        return {
            'metadata': {
                'date': datetime.datetime.now().isoformat(),
                'error': error_msg
            },
            'commits': []
        }

def main():
    args = parse_args()
    debug = args.debug
    
    if debug:
        print("Debug mode enabled")
        print(f"GitLab URL: {args.url}")
        print(f"Output file: {args.output}")
        print(f"Days to look back: {args.days}")
        if args.threads > 0:
            print(f"Using {args.threads} threads")
    
    # Get data using the common function
    data = get_commits_data(
        gitlab_url=args.url,
        admin_token=args.admin_token,
        days=args.days,
        debug=debug,
        threads=args.threads
    )
    
    # Save data based on the specified format
    if args.format == 'json':
        output_file = args.output
        if not output_file.endswith('.json'):
            output_file = f"{os.path.splitext(output_file)[0]}.json"
        print(f"Saving data to {output_file}...")
        save_to_json(data, output_file)
    else:
        print(f"Saving data to {args.output}...")
        save_to_txt(data, args.output)
    
    print("Done!")

if __name__ == "__main__":
    main() 