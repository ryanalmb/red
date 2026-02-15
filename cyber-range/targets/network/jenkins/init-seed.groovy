// =============================================================================
// Jenkins Seed Script — Cyber Range Tier 2 (Corporate)
// =============================================================================
// Runs via Jenkins init.groovy.d on first boot.
// Creates a dummy job with SSH private key in build artifacts.
//
// CORP-04: Credentials stored in plaintext (config.xml)
// CORP-05: LDAP password in Jenkins credentials store
// CORP-10: SSH private key in build artifacts
//
// DO NOT deploy outside the cyber-range.
// =============================================================================

import jenkins.model.*
import hudson.model.*
import com.cloudbees.plugins.credentials.*
import com.cloudbees.plugins.credentials.impl.*
import com.cloudbees.plugins.credentials.domains.*
import hudson.util.Secret
import org.jenkinsci.plugins.plaincredentials.impl.StringCredentialsImpl

def jenkins = Jenkins.instance

// CORP-05: Store LDAP credentials in Jenkins credential store
def domain = Domain.global()
def store = jenkins.getExtensionList('com.cloudbees.plugins.credentials.SystemCredentialsProvider')[0]?.getStore()

if (store != null) {
    def ldapCreds = new UsernamePasswordCredentialsImpl(
        CredentialsScope.GLOBAL,
        'ldap-psyche-local',
        'PSYCHE.LOCAL LDAP Service Account',
        'da_jenkins',
        'JenkinsAdmin2024!'
    )
    store.addCredentials(domain, ldapCreds)
    println('[init-seed] Added LDAP credentials: da_jenkins/JenkinsAdmin2024!')
}

// CORP-10: Create a job with SSH key in workspace/artifacts
def jobName = 'deploy-production'
if (jenkins.getItem(jobName) == null) {
    def job = jenkins.createProject(FreeStyleProject.class, jobName)
    job.description = 'Production deployment pipeline — DO NOT MODIFY'

    // Shell build step that creates an SSH key
    def builder = new hudson.tasks.Shell('''
# Generate deployment SSH key (this ends up in build artifacts)
mkdir -p $WORKSPACE/deploy-keys
cat > $WORKSPACE/deploy-keys/id_rsa << 'SSHKEY'
-----BEGIN OPENSSH PRIVATE KEY-----
b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAMwAAAAtzc2gtZW
QyNTUxOQAAACDFKmGOT2E3VHPnGZJkI4qLGYzNt0ixT3mHy6uEbTgPjAAAAJhK8w/RSvMP
0QAAAAtzc2gtZWQyNTUxOQAAACDFKmGOT2E3VHPnGZJkI4qLGYzNt0ixT3mHy6uEbTgPjA
AAAEDqBs/0Yj5FZVQPy/CxSJjFLlLwLIp1FxN5b0fZGLTfcUqYY5PYTdUc+cZkmQjiosZj
M23SLFPeYfLq4RtOA+MAAAAEGplbmtpbnNAcHN5Y2hlLmxvY2FsAQIDBAUGBw==
-----END OPENSSH PRIVATE KEY-----
SSHKEY
chmod 600 $WORKSPACE/deploy-keys/id_rsa

# Also drop a config note
cat > $WORKSPACE/deploy-keys/README.md << 'README'
# Deployment Keys
- GitLab: ssh -i id_rsa git@gitlab:8082
- FileServer: ssh -i id_rsa jsmith@fileserver01
- DC01: ssh -i id_rsa administrator@dc01
README

echo "Deployment keys staged for production push."
''')
    job.buildersList.add(builder)

    // Archive artifacts so the key is downloadable
    job.publishersList.add(new hudson.tasks.ArtifactArchiver('deploy-keys/**'))

    job.save()
    println("[init-seed] Created job '${jobName}' with SSH key artifacts")
}

println('[init-seed] Jenkins seed complete.')
jenkins.save()
