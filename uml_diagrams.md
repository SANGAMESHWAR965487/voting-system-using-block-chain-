# UML Diagrams for Voting System

## 1. Class Diagram (Database Entities)

```mermaid
classDiagram
    class User {
        -id: int PK
        -name: string
        -rollno: string UK
        -mobile: string
        -email: string
        -password: string
        -voted: bool
        -photo: string
        -approved: bool
    }
    
    class Candidate {
        -id: int PK
        -name: string
        -symbol: string
        -position: string
        -image: string
    }
    
    class Vote {
        -id: int PK
        -rollno: string FK
        -position: string
        -candidate: string
    }
    
    class Setting {
        -key: string PK
        -value: string
    }
    
    User ||--o{ Vote : casts
    Candidate ||--o{ Vote : receives
```

## 2. Component Diagram

```mermaid
graph TD
    subgraph Browser
        Student
        Admin
    end
    
    subgraph Flask_App["Flask App (app.py)"]
        Routes[/Routes<br/>/login /vote /admin/]
        Sessions[Sessions]
        Uploads[File Uploads]
    end
    
    subgraph Database["SQLite DB (voting.db)"]
        Users[Users Table]
        Candidates[Candidates Table]
        Votes[Votes Table]
        Settings[Settings Table]
    end
    
    subgraph Static["Static Files"]
        CSS[CSS]
        JS[JS]
        Images[Uploads/]
    end
    
    Browser -->|HTTP| Routes
    Routes --> Sessions
    Routes --> Uploads
    Routes --> Database
    Routes --> Static
    Uploads --> Images
```

## 3. Sequence Diagram - Student Voting Flow

```mermaid
sequenceDiagram
    participant S as Student
    participant F as Flask App
    participant D as Database
    participant OTP as OTP Store
    
    S->>F: POST /register (name,rollno,mobile,...)
    F->>D: INSERT users (approved=false)
    D-->>F: OK
    
    Note over F: Admin approves user later
    
    S->>F: POST /login (rollno,mobile,password)
    F->>D: SELECT users + verify password
    D-->>F: user data
    F->>OTP: generate/store OTP
    OTP-->>F: OTP
    F-->>S: send_otp response
    
    S->>F: POST /verify_otp (rollno,otp)
    F->>OTP: verify + delete
    OTP-->>F: valid
    F->>S: session[rollno]
    
    S->>F: GET /vote
    F->>D: get_candidates_by_position()
    D-->>F: candidates list
    F-->>S: vote.html
    
    S->>F: POST /submit_vote (selections)
    F->>D: INSERT votes x4 + mark_voted
    D-->>F: OK
    F-->>S: success message
```

## 4. Sequence Diagram - Admin Flow

```mermaid
sequenceDiagram
    participant A as Admin
    participant F as Flask App
    participant D as Database
    
    A->>F: POST /login (admin creds)
    F-->>A: session[admin=true]
    
    A->>F: GET /admin
    F->>D: get_pending_users(), get_all_users(), settings
    D-->>F: data
    F-->>A: admin.html
    
    A->>F: POST /approve_user (rollno)
    F->>D: UPDATE users SET approved=1
    D-->>F: OK
    F-->>A: redirect /admin
    
    A->>F: POST /add_candidate (name,symbol,position,image)
    F->>D: INSERT candidates (check symbol unique)
    D-->>F: OK/duplicate
    F-->>A: message
    
    A->>F: POST /release_results (release/hide)
    F->>D: INSERT/UPDATE settings
    D-->>F: OK
    F-->>A: updated admin page
```

**View Instructions**: Open `uml_diagrams.md` in VSCode/GitHub for interactive Mermaid rendering. Diagrams based on code analysis of app.py, db.py, templates.

