workspace "Safar-e-Taleem" "Evidence-backed C4 model of the Safar-e-Taleem smart school transport platform." {
    !identifiers hierarchical

    model {
        # --- Actors ---
        parent = person "Parent" "Registered parent who tracks their child's school commute, receives transport recommendations, and participates in walking groups or study pods."
        principal = person "Principal" "School principal who monitors fuel costs, manages hybrid schedules, broadcasts curriculum, and oversees all commute activity."

        # --- Software System ---
        safar = softwareSystem "Safar-e-Taleem" "AI-powered platform that cuts school-transport costs for Pakistani families through walking-group clustering, fuel-aware hybrid scheduling, and a Roman-Urdu voice assistant." {

            # --- Containers ---
            webapp = container "Flask Web Application" "Monolithic Python web app serving dashboards, APIs, SSE streams, and the PWA. Hosts all business logic, DB models, and module integrations." "Python 3.12 / Flask" {
                # --- Components (modules) ---
                routes = component "Routes & Auth" "Public/protected routes, login, registration, CSRF, rate limiting, session management." "Flask Blueprints"
                commuteEngine = component "Commute Engine" "DBSCAN clustering (scikit-learn), transport recommendation, fuel cost and carpool saving calculations." "Python / scikit-learn"
                petrolMonitor = component "Petrol Price Monitor" "Scrapes live Pakistani fuel prices, tracks history, detects changes, supports demo spike/reset." "Python / requests"
                schoolRegistry = component "School Registry" "School lookup by name/area, home-to-school distance calculation via Haversine + Nominatim." "Python"
                geoServices = component "Geo Services" "OSRM walking route extraction, Nominatim geocoding with 24h server cache." "Python / requests"
                aiAssistant = component "AI Assistant (Ask Ammi/Abba)" "Qwen (DashScope) chat + voice in Roman-Urdu, with rule-based fallback when no API key is set." "Python / openai SDK"
                notificationEngine = component "Notification Engine" "WhatsApp Cloud API, Pakistani HTTP SMS gateway, IVR delivery. Simulation mode when credentials are absent." "Python / requests"
                curriculumPacks = component "Curriculum Pack Generator" "Offline learning PDF generation (primary/secondary levels), printable packets for families without devices." "Python / xhtml2pdf"
            }

            database = container "SQLite Database" "Stores users, petrol price history, hybrid schedules, live commute locations, and notification logs." "SQLite" {
                tags "Database"
            }

            serviceWorker = container "Service Worker (PWA)" "Offline-first caching of static assets and OpenStreetMap tiles. Installable on mobile." "JavaScript"
        }

        # --- External Systems ---
        osrm = softwareSystem "OSRM Demo Server" "Provides walking-route geometry (waypoints, distance, duration) between coordinates." {
            tags "External"
        }

        nominatim = softwareSystem "Nominatim (OpenStreetMap)" "Free-text address geocoding — resolves typed addresses to Pakistan coordinates." {
            tags "External"
        }

        dashscope = softwareSystem "Alibaba DashScope (Qwen)" "Qwen LLM via OpenAI-compatible SDK. Generates Roman-Urdu + English responses for the AI assistant." {
            tags "External"
        }

        whatsapp = softwareSystem "Meta WhatsApp Cloud API" "Delivers curriculum packets, pod alerts, and SOS notifications to families via WhatsApp." {
            tags "External"
        }

        smsGateway = softwareSystem "Pakistani SMS Gateway" "HTTP SMS gateway (SMS4Connect / Jazz / Telenor) for text-message curriculum delivery." {
            tags "External"
        }

        fuelPriceApi = softwareSystem "Pakistani Fuel Price API" "Shell Pakistan website scraped for live petrol/diesel/kerosene/LPG prices." {
            tags "External"
        }

        # --- Relationships: Actors -> System ---
        parent -> safar "Registers, views dashboard, shares live commute location, receives SOS/alerts, uses AI assistant"
        principal -> safar "Monitors fuel, toggles hybrid schedule, broadcasts curriculum, views all commute activity"

        # --- Container-level relationships ---
        webapp -> database "Reads/writes users, prices, locations, notifications" "SQLAlchemy ORM"
        webapp -> serviceWorker "Serves /sw.js and /manifest.json" "HTTPS"

        # --- Component -> External System relationships ---
        geoServices -> osrm "Walking route requests" "HTTP GET"
        schoolRegistry -> nominatim "Address geocoding" "HTTP GET"
        geoServices -> nominatim "Free-text geocoding" "HTTP GET"
        aiAssistant -> dashscope "Chat completions (Qwen)" "OpenAI-compatible SDK"
        notificationEngine -> whatsapp "WhatsApp message delivery" "HTTPS POST"
        notificationEngine -> smsGateway "SMS delivery" "HTTPS POST"
        petrolMonitor -> fuelPriceApi "Fuel price scraping" "HTTP GET"

        # --- Internal component dependencies ---
        routes -> commuteEngine "Clusters families, recommends transport"
        routes -> petrolMonitor "Live fuel data"
        routes -> schoolRegistry "School info, commute distance"
        routes -> geoServices "Walking routes, geocoding"
        routes -> notificationEngine "SOS dispatch, pod alerts"
        routes -> curriculumPacks "Offline PDF generation"
        aiAssistant -> commuteEngine "Distance, cluster context"
        schoolRegistry -> commuteEngine "Haversine distance_km"
        geoServices -> commuteEngine "Haversine distance_km"
    }

    views {
        systemContext safar "SystemContext" "Safar-e-Taleem system context: actors, the software system, and external integrations." {
            include *
            autoLayout tb
        }

        container safar "Containers" "Internal containers: Flask web app, SQLite database, and PWA service worker." {
            include *
            autoLayout tb
        }

        component webapp "Components" "Internal module components inside the Flask web application." {
            include *
            autoLayout tb
        }

        styles {
            element "Person" {
                shape person
                background #059669
                color #ffffff
            }
            element "Database" {
                shape cylinder
                background #1e40af
                color #ffffff
            }
            element "External" {
                background #6b7280
                color #ffffff
            }
            element "Component" {
                background #0d9488
                color #ffffff
            }
        }
    }
}
