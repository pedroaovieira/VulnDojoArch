You are a senior full-stack and security software engineer.

Design and implement a **Django-based web application** for **local vulnerability management**, acting as a **local repository of security information scattered across the Internet**.

### 1. General Architecture Requirements

* **Framework:** Django (latest LTS)

* **Database:** SQLite

* **Application Server:** Waitress

* **Containers:** **NOT allowed** (no Docker, Podman, etc.)

* **Deployment targets:**

* Linux

* Windows

* Provide clear instructions for running the application on both platforms.

* Use **virtualenv** (or venv) for dependency management.

* Code must be production-ready, modular, and extensible.

### 2. Frontend / UI Requirements

* The web UI must be based on the **AdminLTE 3.2.0 dashboard template**.

* Assume AdminLTE-3.2.0 already exists in a local folder named:

```

AdminLTE-3.2.0/

```

* Integrate AdminLTE cleanly with Django templates and static files.

* Provide:

* Dashboard overview

* Search interfaces

* Detail pages

* Pagination and filtering

* UI should be consistent across all apps.

### 3. Application Purpose

The application is a **local vulnerability management dashboard** whose main goals are:

* Act as a **local mirror / repository** of public vulnerability data

* Allow **searching, browsing, and managing** this data

* Be **extensible**, allowing new Django apps to be added later

### 4. Django Apps to Implement

#### App 1: CPE Repository

* Purpose: Local repository of the **NVD Official Common Platform Enumeration (CPE) Dictionary**

* Data source:

* Documentation: [https://nvd.nist.gov/products/cpe](https://nvd.nist.gov/products/cpe)

* API endpoint:

```

https://services.nvd.nist.gov/rest/json/cpes/2.0/

```

* Requirements:

* Import CPE data using the NVD API

* Handle pagination (`resultsPerPage`, `startIndex`)

* Store normalized CPE data in SQLite

* Implement:

* Initial full import

* **Automatic regular updates** (scheduled task)

* Provide:

* Web UI for browsing and searching CPEs

* REST API endpoints for querying CPE data

#### App 2: CVE Repository

* Purpose: Local repository of **NVD CVE data**

* Data source:

* Documentation: [https://nvd.nist.gov/developers/vulnerabilities](https://nvd.nist.gov/developers/vulnerabilities)

* API endpoint:

```

https://services.nvd.nist.gov/rest/json/cves/2.0/

```

* Requirements:

* Import CVE data via NVD API

* Handle pagination and large datasets

* Store CVEs, severity, CVSS, affected products, references

* Implement:

* Initial import

* **Automatic regular updates**

* Provide:

* Web UI for CVE browsing, filtering, and search

* REST API endpoints for CVE data

#### App 3: Linux CVE Announcements Repository

* Purpose: Local repository of **Linux CVE Announcements**

* Data source:

* Archive: [https://lore.kernel.org/linux-cve-announce/](https://lore.kernel.org/linux-cve-announce/)

* Mirroring instructions:

```

https://lore.kernel.org/linux-cve-announce/_/text/mirror/

```

* Requirements:

* Mirror the mailing list archive locally following official instructions

* Parse announcements into structured data

* Store in SQLite

* Implement:

* Initial mirror

* **Automatic periodic updates**

* Provide:

* Web UI to browse announcements

* REST API for querying announcements

### 5. APIs

* All apps must expose **REST APIs** using Django REST Framework:

* Search

* List

* Detail views

* APIs should be:

* Read-optimized

* Paginated

* Filterable

### 6. Background Jobs & Updates

* Implement scheduled update mechanisms:

* Django management commands

* Task scheduling compatible with Linux (cron) and Windows (Task Scheduler)

* Do **NOT** rely on Celery or external brokers unless strictly necessary.

### 7. Security & Best Practices

* Follow Django security best practices

* Use environment variables for configuration

* Handle NVD API rate limits gracefully

* Log import/update activity

### 8. Extensibility

* Project structure must allow:

* Easy addition of new data-source apps

* Shared base models, utilities, and UI components

### 9. Guidance Repositories

Use the following repositories as **reference and guidance**, not as containers:

* [https://github.com/pedroaovieira/hello_world_django_iis](https://github.com/pedroaovieira/hello_world_django_iis)

* [https://github.com/pedroaovieira/cpe](https://github.com/pedroaovieira/cpe)

### 10. Deliverables

Provide:

1. Project structure

2. Django settings and configuration

3. Models, views, serializers, URLs

4. Import/update logic

5. AdminLTE integration

6. REST API examples

7. Linux and Windows deployment instructions

8. Clear explanation of how to add new apps later

---

**Important:**

Do not use containers. The solution must run natively on Linux and Windows using Python, Django, SQLite, and Waitress.