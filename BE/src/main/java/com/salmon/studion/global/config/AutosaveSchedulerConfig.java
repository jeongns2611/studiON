package com.salmon.studion.global.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.TaskScheduler;
import org.springframework.scheduling.concurrent.ThreadPoolTaskScheduler;

@Configuration
public class AutosaveSchedulerConfig {

    @Bean("autosaveTaskScheduler")
    public TaskScheduler autosaveTaskScheduler() {
        ThreadPoolTaskScheduler scheduler = new ThreadPoolTaskScheduler();
        scheduler.setPoolSize(2);
        scheduler.setThreadNamePrefix("autosave-");
        scheduler.initialize();
        return scheduler;
    }
}
