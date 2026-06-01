pipeline {
    agent any

    options {
        timestamps()
        disableConcurrentBuilds()
        skipDefaultCheckout(true)
    }

    environment {
        COMPOSE_PROJECT_NAME = 'studion'
    }

    stages {
        stage('Checkout') {
            steps {
                deleteDir()
                checkout scm
            }
        }

        stage('CI - Backend Build') {
            steps {
                dir('BE') {
                    sh './gradlew clean build'
                }
            }
        }
        
        stage('CI - Frontend Build') {
            steps {
                dir('FE') {
                    sh 'docker build --target builder -t studion-fe-ci:${BUILD_NUMBER} .'
                }
            }
        }

        stage('CI - AI Build') {

            agent {
                label 'ai-server'
            }
            steps {
                sh '''
                cd /home/ec2-user/deploy/S14P31A205
                git fetch origin release
                git checkout release
                git pull --ff-only origin release
                docker compose --env-file .env.ai -f compose.ai.yaml build
                '''
            }
        }
        
        stage('Prepare Env') {
            steps {
                withCredentials([file(credentialsId: 'studion-prod-env', variable: 'ENV_PROD_FILE')]) {
                    sh 'rm -f .env.prod && cp "$ENV_PROD_FILE" .env.prod && chmod 600 .env.prod'
                }
            }
        }
        
        stage('CD - Build App') {
            steps {
                sh 'docker compose --env-file .env.prod -f compose.prod.yaml build'
            }
        }
        
        stage('CD - Deploy App') {
            steps {
                sh 'docker compose --env-file .env.prod -f compose.prod.yaml up -d --remove-orphans'
            }
        }
        
        stage('CD - Deploy AI') {
            when {
                beforeAgent true
                branch 'release'
            }
            agent {
                label 'ai-server'
            }
            steps {
                sh '''
                cd /home/ec2-user/deploy/S14P31A205
                docker compose --env-file .env.ai -f compose.ai.yaml up -d --scale ai-worker=3
                docker compose --env-file .env.ai -f compose.ai.yaml ps
                '''
            }
        }
        
        stage('CD - Status App') {
            steps {
                sh 'docker compose --env-file .env.prod -f compose.prod.yaml ps'
            }
        }
    }
    post {
        always {
            sh 'rm -f .env.prod'
        }
    }
}
