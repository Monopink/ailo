#!/usr/bin/env node

/**
 * Generate version.json file for automatic cache busting
 */

const fs = require('fs')
const path = require('path')

// Generate version based on current timestamp
const version = Date.now().toString()

// Create version object
const versionData = {
  version: version,
  timestamp: new Date().toISOString(),
  build: process.env.NODE_ENV || 'development'
}

// Write to public directory
const publicDir = path.join(__dirname, 'public')
const versionFile = path.join(publicDir, 'version.json')

// Ensure public directory exists
if (!fs.existsSync(publicDir)) {
  fs.mkdirSync(publicDir, { recursive: true })
}

// Write version file
fs.writeFileSync(versionFile, JSON.stringify(versionData, null, 2))

console.log(`✅ Generated version.json: ${version}`)
console.log(`📁 File location: ${versionFile}`)

// Also update .env file with new version
const envFile = path.join(__dirname, '.env.local')
let envContent = ''

// Read existing .env.local if it exists
if (fs.existsSync(envFile)) {
  envContent = fs.readFileSync(envFile, 'utf8')
}

// Update or add VITE_APP_VERSION
const versionLine = `VITE_APP_VERSION=${version}`
const lines = envContent.split('\n')
const versionLineIndex = lines.findIndex(line => line.startsWith('VITE_APP_VERSION='))

if (versionLineIndex >= 0) {
  lines[versionLineIndex] = versionLine
} else {
  lines.push(versionLine)
}

// Write back to .env.local
fs.writeFileSync(envFile, lines.join('\n'))

console.log(`✅ Updated .env.local with version: ${version}`)
