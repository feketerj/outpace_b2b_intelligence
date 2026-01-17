// MongoDB initialization script
// Creates application database and user with restricted permissions
//
// This script runs automatically when MongoDB container starts for the first time
// It uses environment variables passed to the container

// Read environment variables (set via docker-compose)
const appDb = process.env.DB_NAME || 'outpace_intelligence';
const appUser = process.env.MONGO_APP_USERNAME || 'app';
const appPassword = process.env.MONGO_APP_PASSWORD;

if (!appPassword) {
    print('ERROR: MONGO_APP_PASSWORD environment variable is required');
    quit(1);
}

print(`Creating database: ${appDb}`);
print(`Creating user: ${appUser}`);

// Switch to the application database
db = db.getSiblingDB(appDb);

// Create application user with readWrite permissions on this database only
db.createUser({
    user: appUser,
    pwd: appPassword,
    roles: [
        {
            role: 'readWrite',
            db: appDb
        }
    ]
});

print(`User ${appUser} created successfully with readWrite access to ${appDb}`);

// Create initial indexes for performance
db.tenants.createIndex({ 'slug': 1 }, { unique: true });
db.tenants.createIndex({ 'status': 1 });
db.users.createIndex({ 'email': 1 }, { unique: true });
db.users.createIndex({ 'tenant_id': 1 });
db.opportunities.createIndex({ 'tenant_id': 1, 'captured_date': -1 });
db.opportunities.createIndex({ 'tenant_id': 1, 'external_id': 1 }, { unique: true });

print('Initial indexes created');
