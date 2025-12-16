
export interface CommunityPost {
  id: string;
  user: {
    name: string;
    avatar: string;
  };
  action: string;
  timeAgo: string;
  content: string;
  image?: string;
  stats?: {
    label: string;
    value: string;
  }[];
  likes: number;
  comments: number;
}

export interface Challenge {
  id: string;
  title: string;
  participants: string;
  image: string;
  description: string;
  joined: boolean;
  timeLeft: string;
}

export interface Friend {
  id: string;
  name: string;
  avatar: string;
  status: 'Online' | 'Offline' | 'In a Workout';
  lastActive: string;
  streak: number;
}

export interface CommunityGoal {
  id: string;
  title: string;
  description: string;
  currentValue: number;
  targetValue: number;
  unit: string;
  participants: number;
  image: string;
  color: string;
}

export const communityFeed: CommunityPost[] = [
  {
    id: 'post_1',
    user: {
      name: 'Jane Doe',
      avatar: 'https://randomuser.me/api/portraits/women/44.jpg'
    },
    action: 'Completed a run',
    timeAgo: '2h ago',
    content: 'Great pace today! Felt energized despite the humidity.',
    image: 'https://images.pexels.com/photos/3757942/pexels-photo-3757942.jpeg?auto=compress&cs=tinysrgb&w=800',
    stats: [
      { label: 'Distance', value: '5.01 km' },
      { label: 'Time', value: '28:32 min' },
      { label: 'Pace', value: '5\'41" /km' }
    ],
    likes: 24,
    comments: 3
  },
  {
    id: 'post_2',
    user: {
      name: 'John Smith',
      avatar: 'https://randomuser.me/api/portraits/men/32.jpg'
    },
    action: 'Completed a workout',
    timeAgo: '8h ago',
    content: 'Hit a new personal best on the bench press! Consistency is key.',
    stats: [
      { label: 'Duration', value: '1h 15m' },
      { label: 'Calories', value: '320 kcal' },
      { label: 'Volume', value: '4,500 kg' }
    ],
    likes: 45,
    comments: 7
  },
  {
    id: 'post_3',
    user: {
      name: 'Sarah Connor',
      avatar: 'https://randomuser.me/api/portraits/women/68.jpg'
    },
    action: 'Joined a challenge',
    timeAgo: '1d ago',
    content: 'Just signed up for the 30-Day Yoga Journey. Who\'s with me?',
    image: 'https://images.pexels.com/photos/3823039/pexels-photo-3823039.jpeg?auto=compress&cs=tinysrgb&w=800',
    likes: 18,
    comments: 12
  },
    {
    id: 'post_4',
    user: {
      name: 'Alex Johnson',
      avatar: 'https://randomuser.me/api/portraits/men/45.jpg'
    },
    action: 'Completed a hike',
    timeAgo: '3h ago',
    content: 'The view from the summit was absolutely worth the climb. 🏔️',
    image: 'https://images.pexels.com/photos/1365425/pexels-photo-1365425.jpeg?auto=compress&cs=tinysrgb&w=800',
    stats: [
      { label: 'Elevation', value: '850m' },
      { label: 'Distance', value: '12.4 km' },
      { label: 'Time', value: '3h 10m' }
    ],
    likes: 156,
    comments: 24
  },
  {
    id: 'post_5',
    user: {
      name: 'Maria Garcia',
      avatar: 'https://randomuser.me/api/portraits/women/65.jpg'
    },
    action: 'Prepared a meal',
    timeAgo: '5h ago',
    content: 'Fueling up for tomorrow\'s marathon training. Quinoa bowl with roasted veggies!',
    image: 'https://images.pexels.com/photos/1640777/pexels-photo-1640777.jpeg?auto=compress&cs=tinysrgb&w=800',
    stats: [
      { label: 'Protein', value: '35g' },
      { label: 'Carbs', value: '65g' },
      { label: 'Calories', value: '550' }
    ],
    likes: 89,
    comments: 15
  },
  {
    id: 'post_6',
    user: {
      name: 'David Chen',
      avatar: 'https://randomuser.me/api/portraits/men/22.jpg'
    },
    action: 'Completed a swim',
    timeAgo: '12h ago',
    content: 'Morning laps are the best way to start the day. Water was freezing though! 🥶',
    image: 'https://images.pexels.com/photos/863988/pexels-photo-863988.jpeg?auto=compress&cs=tinysrgb&w=800',
    stats: [
      { label: 'Laps', value: '40' },
      { label: 'Distance', value: '2.0 km' },
      { label: 'Pace', value: '2:15 /100m' }
    ],
    likes: 67,
    comments: 8
  },
  {
    id: 'post_7',
    user: {
      name: 'Emma Wilson',
      avatar: 'https://randomuser.me/api/portraits/women/90.jpg'
    },
    action: 'Did a meditation session',
    timeAgo: '30m ago',
    content: '15 minutes of mindfulness to reset the mental state.',
    stats: [
      { label: 'Duration', value: '15 min' },
      { label: 'Focus', value: 'Anxiety' }
    ],
    likes: 12,
    comments: 0
  },
    {
    id: 'post_8',
    user: {
      name: 'Carlos Mendez',
      avatar: 'https://randomuser.me/api/portraits/men/86.jpg'
    },
    action: 'Completed a ride',
    timeAgo: '45m ago',
    content: 'Sunday morning climb. The legs were burning but the fresh air was worth it! 🚴‍♂️',
    image: 'http://googleusercontent.com/image_collection/image_retrieval/6791787532587630055_0',
    stats: [
      { label: 'Distance', value: '45.2 km' },
      { label: 'Elevation', value: '620m' },
      { label: 'Avg Speed', value: '24 km/h' }
    ],
    likes: 112,
    comments: 18
  },
  {
    id: 'post_9',
    user: {
      name: 'Sophie Anderson',
      avatar: 'https://randomuser.me/api/portraits/women/28.jpg'
    },
    action: 'Finished a race',
    timeAgo: '2h ago',
    content: 'Officially a marathon finisher! 🏅 Can’t believe I actually did it. Thank you everyone for the support!',
    image: 'http://googleusercontent.com/image_collection/image_retrieval/10352388836293259691_0',
    stats: [
      { label: 'Distance', value: '42.2 km' },
      { label: 'Time', value: '3h 58m' },
      { label: 'Place', value: 'Finisher' }
    ],
    likes: 345,
    comments: 82
  },
  {
    id: 'post_10',
    user: {
      name: 'Liam O\'Connor',
      avatar: 'https://randomuser.me/api/portraits/men/3.jpg'
    },
    action: 'Logged nutrition',
    timeAgo: '4h ago',
    content: 'Post-workout recovery fuel. Spinach, banana, protein powder, and almond milk. 🥤',
    image: 'http://googleusercontent.com/image_collection/image_retrieval/13875703328026381233_0',
    stats: [
      { label: 'Calories', value: '420' },
      { label: 'Protein', value: '30g' },
      { label: 'Fat', value: '12g' }
    ],
    likes: 45,
    comments: 5
  },
  {
    id: 'post_11',
    user: {
      name: 'Priya Sharma',
      avatar: 'https://randomuser.me/api/portraits/women/76.jpg'
    },
    action: 'Completed a group class',
    timeAgo: '6h ago',
    content: 'Crushed the HIIT class with the squad tonight! Energy was off the charts. 🔥',
    image: 'http://googleusercontent.com/image_collection/image_retrieval/12512309872197528216_0',
    stats: [
      { label: 'Duration', value: '45 min' },
      { label: 'Avg HR', value: '155 bpm' },
      { label: 'Cal Burn', value: '380' }
    ],
    likes: 88,
    comments: 14
  },
  {
    id: 'post_12',
    user: {
      name: 'Marcus Johnson',
      avatar: 'https://randomuser.me/api/portraits/men/62.jpg'
    },
    action: 'Completed a night run',
    timeAgo: '10h ago',
    content: 'City lights and empty streets. Perfect way to clear the head after a long week.',
    image: 'http://googleusercontent.com/image_collection/image_retrieval/3853362189332394803_0',
    stats: [
      { label: 'Distance', value: '8.5 km' },
      { label: 'Pace', value: '5\'20" /km' },
      { label: 'Time', value: '45:10' }
    ],
    likes: 92,
    comments: 9
  },
  
  {
    id: 'post_13',
    user: { name: 'Kevin Hart', avatar: 'https://randomuser.me/api/portraits/men/14.jpg' },
    action: 'Completed a leg workout',
    timeAgo: '11h ago',
    content: 'Never skip leg day! Squats felt heavy but moving well today. 🏋️‍♂️',
    image: 'https://images.pexels.com/photos/841130/pexels-photo-841130.jpeg?auto=compress&cs=tinysrgb&w=800',
    stats: [
      { label: 'Squat', value: '140 kg' },
      { label: 'Sets', value: '5' },
      { label: 'Reps', value: '5' }
    ],
    likes: 210,
    comments: 45
  },
  {
    id: 'post_14',
    user: { name: 'Olivia Brown', avatar: 'https://randomuser.me/api/portraits/women/42.jpg' },
    action: 'Did a sunset yoga flow',
    timeAgo: '14h ago',
    content: 'Finding balance as the sun goes down. The perfect way to end the day.',
    image: 'https://images.pexels.com/photos/3756523/pexels-photo-3756523.jpeg?auto=compress&cs=tinysrgb&w=800',
    stats: [
      { label: 'Duration', value: '30 min' },
      { label: 'Type', value: 'Vinyasa' },
      { label: 'Mood', value: 'Calm' }
    ],
    likes: 89,
    comments: 6
  },
  {
    id: 'post_15',
    user: { name: 'Daniel Kim', avatar: 'https://randomuser.me/api/portraits/men/36.jpg' },
    action: 'Cycled to work',
    timeAgo: '1d ago',
    content: 'Beating traffic and burning calories. Commute metrics looking good.',
    image: 'https://images.pexels.com/photos/100582/pexels-photo-100582.jpeg?auto=compress&cs=tinysrgb&w=800',
    stats: [
      { label: 'Distance', value: '12 km' },
      { label: 'Time', value: '35 min' },
      { label: 'CO2 Saved', value: '2.4 kg' }
    ],
    likes: 56,
    comments: 12
  },
  {
    id: 'post_16',
    user: { name: 'Rachel Green', avatar: 'https://randomuser.me/api/portraits/women/50.jpg' },
    action: 'Went rock climbing',
    timeAgo: '1d ago',
    content: 'Finally sent that V5 project I\'ve been working on for weeks! 🧗‍♀️',
    image: 'https://images.pexels.com/photos/12711413/pexels-photo-12711413.jpeg?auto=compress&cs=tinysrgb&w=800',
    stats: [
      { label: 'Grade', value: 'V5' },
      { label: 'Attempts', value: '4' },
      { label: 'Session', value: '2h' }
    ],
    likes: 134,
    comments: 22
  },
  {
    id: 'post_17',
    user: { name: 'Tom Hardy', avatar: 'https://randomuser.me/api/portraits/men/78.jpg' },
    action: 'Played Tennis',
    timeAgo: '1d ago',
    content: 'Great match against a tough opponent. Tie-break in the second set was intense!',
    image: 'https://images.pexels.com/photos/5741298/pexels-photo-5741298.jpeg?auto=compress&cs=tinysrgb&w=800',
    stats: [
      { label: 'Score', value: '6-4, 7-6' },
      { label: 'Aces', value: '8' },
      { label: 'Duration', value: '1h 45m' }
    ],
    likes: 67,
    comments: 9
  },
  {
    id: 'post_18',
    user: { name: 'Anita Roy', avatar: 'https://randomuser.me/api/portraits/women/66.jpg' },
    action: 'Prepared a healthy lunch',
    timeAgo: '1d ago',
    content: 'Salmon avocado salad with lemon dressing. Omega-3 power! 🐟🥑',
    image: 'https://images.pexels.com/photos/1640772/pexels-photo-1640772.jpeg?auto=compress&cs=tinysrgb&w=800',
    stats: [
      { label: 'Protein', value: '42g' },
      { label: 'Fats', value: '25g' },
      { label: 'Carbs', value: '12g' }
    ],
    likes: 215,
    comments: 31
  },
  {
    id: 'post_19',
    user: { name: 'Chris Evans', avatar: 'https://randomuser.me/api/portraits/men/5.jpg' },
    action: 'Went for a Trail Run',
    timeAgo: '2d ago',
    content: 'Muddy trails and steep hills. Training for the ultra is getting serious.',
    image: 'https://images.pexels.com/photos/1571939/pexels-photo-1571939.jpeg?auto=compress&cs=tinysrgb&w=800',
    stats: [
      { label: 'Distance', value: '18 km' },
      { label: 'Elevation', value: '950m' },
      { label: 'Pace', value: '6\'30" /km' }
    ],
    likes: 312,
    comments: 54
  },
  {
    id: 'post_20',
    user: { name: 'Diana Prince', avatar: 'https://randomuser.me/api/portraits/women/33.jpg' },
    action: 'Completed a swim session',
    timeAgo: '2d ago',
    content: 'Working on my freestyle technique. Glide is feeling much better.',
    image: 'https://images.pexels.com/photos/1263348/pexels-photo-1263348.jpeg?auto=compress&cs=tinysrgb&w=800',
    stats: [
      { label: 'Distance', value: '1500m' },
      { label: 'Laps', value: '30' },
      { label: 'Time', value: '32 min' }
    ],
    likes: 78,
    comments: 11
  },
  {
    id: 'post_21',
    user: { name: 'Mike Ross', avatar: 'https://randomuser.me/api/portraits/men/11.jpg' },
    action: 'Played Basketball',
    timeAgo: '2d ago',
    content: 'Pickup game at the local park. Got the W!',
    image: 'https://images.pexels.com/photos/1752757/pexels-photo-1752757.jpeg?auto=compress&cs=tinysrgb&w=800',
    stats: [
      { label: 'Points', value: '22' },
      { label: 'Assists', value: '5' },
      { label: 'Rebounds', value: '8' }
    ],
    likes: 104,
    comments: 23
  },
  {
    id: 'post_22',
    user: { name: 'Jessica Pearson', avatar: 'https://randomuser.me/api/portraits/women/59.jpg' },
    action: 'Did Pilates',
    timeAgo: '2d ago',
    content: 'Core is on fire 🔥. Reformer pilates is a game changer.',
    image: 'https://images.pexels.com/photos/416778/pexels-photo-416778.jpeg?auto=compress&cs=tinysrgb&w=800',
    stats: [
      { label: 'Class', value: 'Advanced' },
      { label: 'Time', value: '50 min' },
      { label: 'Burn', value: '280 kcal' }
    ],
    likes: 65,
    comments: 8
  },
  {
    id: 'post_23',
    user: { name: 'Bruce Wayne', avatar: 'https://randomuser.me/api/portraits/men/99.jpg' },
    action: 'Completed a Rowing Session',
    timeAgo: '3d ago',
    content: '2k time trial today. New PB!',
    image: 'https://images.pexels.com/photos/1192043/pexels-photo-1192043.jpeg?auto=compress&cs=tinysrgb&w=800',
    stats: [
      { label: 'Distance', value: '2000m' },
      { label: 'Time', value: '6:45' },
      { label: 'Split', value: '1:41 /500m' }
    ],
    likes: 145,
    comments: 19
  },
  {
    id: 'post_24',
    user: { name: 'Natasha Romanoff', avatar: 'https://randomuser.me/api/portraits/women/19.jpg' },
    action: 'Practiced Boxing',
    timeAgo: '3d ago',
    content: 'Bag work and sparring. Working on speed and footwork.',
    image: 'https://images.pexels.com/photos/4761793/pexels-photo-4761793.jpeg?auto=compress&cs=tinysrgb&w=800',
    stats: [
      { label: 'Rounds', value: '12' },
      { label: 'Avg HR', value: '165 bpm' },
      { label: 'Duration', value: '1h' }
    ],
    likes: 290,
    comments: 35
  },
  {
    id: 'post_25',
    user: { name: 'Peter Parker', avatar: 'https://randomuser.me/api/portraits/men/29.jpg' },
    action: 'Went Skateboarding',
    timeAgo: '3d ago',
    content: 'Finally landed the kickflip! 🛹',
    image: 'https://images.pexels.com/photos/1017058/pexels-photo-1017058.jpeg?auto=compress&cs=tinysrgb&w=800',
    stats: [
      { label: 'Tricks', value: '15' },
      { label: 'Falls', value: '3' },
      { label: 'Fun', value: '100%' }
    ],
    likes: 420,
    comments: 67
  },
  {
    id: 'post_26',
    user: { name: 'Wanda Maximoff', avatar: 'https://randomuser.me/api/portraits/women/88.jpg' },
    action: 'Went Hiking',
    timeAgo: '3d ago',
    content: 'Reconnecting with nature. The silence here is beautiful.',
    image: 'https://images.pexels.com/photos/2386226/pexels-photo-2386226.jpeg?auto=compress&cs=tinysrgb&w=800',
    stats: [
      { label: 'Elevation', value: '400m' },
      { label: 'Steps', value: '15,000' },
      { label: 'Views', value: '∞' }
    ],
    likes: 180,
    comments: 21
  },
  {
    id: 'post_27',
    user: { name: 'Tony Stark', avatar: 'https://randomuser.me/api/portraits/men/4.jpg' },
    action: 'Used the Treadmill',
    timeAgo: '4d ago',
    content: 'Too rainy outside, so got the miles in indoors. Netflix and run.',
    image: 'https://images.pexels.com/photos/1954524/pexels-photo-1954524.jpeg?auto=compress&cs=tinysrgb&w=800',
    stats: [
      { label: 'Distance', value: '5 km' },
      { label: 'Incline', value: '2%' },
      { label: 'Pace', value: '5\'00" /km' }
    ],
    likes: 110,
    comments: 15
  },
  {
    id: 'post_28',
    user: { name: 'Carol Danvers', avatar: 'https://randomuser.me/api/portraits/women/95.jpg' },
    action: 'Crossfit WOD',
    timeAgo: '4d ago',
    content: 'That was brutal. "Murph" complete. Respect to the fallen.',
    image: 'https://images.pexels.com/photos/1552249/pexels-photo-1552249.jpeg?auto=compress&cs=tinysrgb&w=800',
    stats: [
      { label: 'Pull-ups', value: '100' },
      { label: 'Push-ups', value: '200' },
      { label: 'Squats', value: '300' }
    ],
    likes: 350,
    comments: 50
  },
  {
    id: 'post_29',
    user: { name: 'Steve Rogers', avatar: 'https://randomuser.me/api/portraits/men/50.jpg' },
    action: 'Calisthenics Workout',
    timeAgo: '5d ago',
    content: 'Just bodyweight today. Focusing on form and control.',
    image: 'https://images.pexels.com/photos/1480520/pexels-photo-1480520.jpeg?auto=compress&cs=tinysrgb&w=800',
    stats: [
      { label: 'Muscle Ups', value: '10' },
      { label: 'Plank', value: '5 min' },
      { label: 'Dips', value: '50' }
    ],
    likes: 405,
    comments: 60
  },
  {
    id: 'post_30',
    user: { name: 'Jean Grey', avatar: 'https://randomuser.me/api/portraits/women/24.jpg' },
    action: 'Jump Rope Cardio',
    timeAgo: '5d ago',
    content: 'Quick 20 minute burner. Coordination is improving!',
    image: 'https://images.pexels.com/photos/4426514/pexels-photo-4426514.jpeg?auto=compress&cs=tinysrgb&w=800',
    stats: [
      { label: 'Jumps', value: '1800' },
      { label: 'Calories', value: '250' },
      { label: 'Trips', value: '4' }
    ],
    likes: 95,
    comments: 13
  }

];

export const challengesData: Challenge[] = [
  {
    id: 'c_1',
    title: 'Monthly 100km Run',
    participants: '1,204 participants',
    image: 'https://images.pexels.com/photos/2402777/pexels-photo-2402777.jpeg?auto=compress&cs=tinysrgb&w=800',
    description: 'Run a total of 100km this month. Track your progress and climb the leaderboard.',
    joined: true,
    timeLeft: '12 days left'
  },
  {
    id: 'c_2',
    title: 'Weekend Warrior HIIT',
    participants: '897 participants',
    image: 'https://images.pexels.com/photos/2294361/pexels-photo-2294361.jpeg?auto=compress&cs=tinysrgb&w=800',
    description: 'Complete 2 HIIT workouts every weekend for a month.',
    joined: false,
    timeLeft: 'Starts Saturday'
  },
  {
    id: 'c_3',
    title: 'Team Cycle Quest',
    participants: '45 teams',
    image: 'https://images.pexels.com/photos/248547/pexels-photo-248547.jpeg?auto=compress&cs=tinysrgb&w=800',
    description: 'Form a team of 4 and cycle the distance of the Tour de France together.',
    joined: false,
    timeLeft: 'Registration Open'
  },
    {
    id: 'c_4',
    title: 'The Hydration Hero',
    participants: '5,430 participants',
    image: 'https://images.pexels.com/photos/416528/pexels-photo-416528.jpeg?auto=compress&cs=tinysrgb&w=800',
    description: 'Track your water intake for 30 days. Goal: 3 liters per day.',
    joined: true,
    timeLeft: '15 days left'
  },
  {
    id: 'c_5',
    title: 'Morning Risers Yoga',
    participants: '2,100 participants',
    image: 'https://images.pexels.com/photos/3822864/pexels-photo-3822864.jpeg?auto=compress&cs=tinysrgb&w=800',
    description: 'Complete a 20-minute flow every morning before 8 AM.',
    joined: false,
    timeLeft: 'Starts Monday'
  },
  {
    id: 'c_6',
    title: 'Iron Man Prep: Swim',
    participants: '320 participants',
    image: 'https://images.pexels.com/photos/1263349/pexels-photo-1263349.jpeg?auto=compress&cs=tinysrgb&w=800',
    description: 'Advanced swimming intervals for triathlon preparation.',
    joined: false,
    timeLeft: 'Registration Closing Soon'
  },
  {
    id: 'c_7',
    title: 'Sugar-Free Streak',
    participants: '3,150 participants',
    image: 'https://images.pexels.com/photos/1132047/pexels-photo-1132047.jpeg?auto=compress&cs=tinysrgb&w=800',
    description: 'Cut out processed sugar for 14 days. Focus on whole foods and natural energy.',
    joined: true,
    timeLeft: '5 days left'
  },
  {
    id: 'c_8',
    title: 'The 10k Daily Step Challenge',
    participants: '12,400 participants',
    image: 'https://images.pexels.com/photos/601177/pexels-photo-601177.jpeg?auto=compress&cs=tinysrgb&w=800',
    description: 'Hit 10,000 steps every single day for a month. Keep moving!',
    joined: false,
    timeLeft: 'Starts 1st of Month'
  },
  {
    id: 'c_9',
    title: 'Core Crusher Week',
    participants: '850 participants',
    image: 'https://images.pexels.com/photos/2294354/pexels-photo-2294354.jpeg?auto=compress&cs=tinysrgb&w=800',
    description: '7 days of ab-focused workouts. 10 minutes a day to build a steel core.',
    joined: false,
    timeLeft: 'Ends in 2 days'
  },
  {
    id: 'c_10',
    title: 'Zen Master Sleep Goal',
    participants: '4,200 participants',
    image: 'https://images.pexels.com/photos/355863/pexels-photo-355863.jpeg?auto=compress&cs=tinysrgb&w=800',
    description: 'Log at least 7.5 hours of sleep for 5 nights in a row.',
    joined: true,
    timeLeft: 'Ongoing'
  },
  {
    id: 'c_11',
    title: 'King of the Mountain',
    participants: '1,100 participants',
    image: 'https://images.pexels.com/photos/100582/pexels-photo-100582.jpeg?auto=compress&cs=tinysrgb&w=800',
    description: 'Cycling challenge: Climb a total of 2,000m vertical elevation this weekend.',
    joined: false,
    timeLeft: 'Starts Saturday'
  },
  {
    id: 'c_12',
    title: 'Veggie Variety',
    participants: '2,890 participants',
    image: 'https://images.pexels.com/photos/1351238/pexels-photo-1351238.jpeg?auto=compress&cs=tinysrgb&w=800',
    description: 'Eat 30 different types of plants (fruits, veg, nuts, seeds) in a week.',
    joined: false,
    timeLeft: 'Registration Open'
  }

];

export const friendsData: Friend[] = [
  {
    id: 'f_1',
    name: 'Michael Chen',
    avatar: 'https://randomuser.me/api/portraits/men/11.jpg',
    status: 'In a Workout',
    lastActive: 'Now',
    streak: 15
  },
  {
    id: 'f_2',
    name: 'Emily Rose',
    avatar: 'https://randomuser.me/api/portraits/women/12.jpg',
    status: 'Online',
    lastActive: '5m ago',
    streak: 3
  },
  {
    id: 'f_3',
    name: 'David Kim',
    avatar: 'https://randomuser.me/api/portraits/men/22.jpg',
    status: 'Offline',
    lastActive: '2h ago',
    streak: 0
  },
  {
    id: 'f_4',
    name: 'Lisa Patel',
    avatar: 'https://randomuser.me/api/portraits/women/33.jpg',
    status: 'Offline',
    lastActive: '1d ago',
    streak: 22
  },
    {
    id: 'f_5',
    name: 'Robert Fox',
    avatar: 'https://randomuser.me/api/portraits/men/54.jpg',
    status: 'In a Workout',
    lastActive: 'Now',
    streak: 45
  },
  {
    id: 'f_6',
    name: 'Amanda Lowery',
    avatar: 'https://randomuser.me/api/portraits/women/55.jpg',
    status: 'Online',
    lastActive: '1m ago',
    streak: 12
  },
  {
    id: 'f_7',
    name: 'James Wilson',
    avatar: 'https://randomuser.me/api/portraits/men/76.jpg',
    status: 'Offline',
    lastActive: '3d ago',
    streak: 0
  },
  {
    id: 'f_8',
    name: 'Sofia Martinez',
    avatar: 'https://randomuser.me/api/portraits/women/89.jpg',
    status: 'In a Workout',
    lastActive: 'Now',
    streak: 8
  }
];

export const communityGoals: CommunityGoal[] = [
  {
    id: 'cg_1',
    title: 'Walk Across America',
    description: 'A collective goal for the entire community to walk 100,000 miles.',
    currentValue: 67450,
    targetValue: 100000,
    unit: 'miles',
    participants: 12500,
    image: 'https://images.pexels.com/photos/1450082/pexels-photo-1450082.jpeg?auto=compress&cs=tinysrgb&w=800',
    color: 'from-blue-600 to-indigo-600'
  },
  {
    id: 'cg_2',
    title: 'Billion Heartbeats',
    description: 'Collectively log 1 billion minutes of elevated heart rate activity.',
    currentValue: 890000000,
    targetValue: 1000000000,
    unit: 'mins',
    participants: 45000,
    image: 'https://images.pexels.com/photos/416778/pexels-photo-416778.jpeg?auto=compress&cs=tinysrgb&w=800',
    color: 'from-red-600 to-pink-600'
  },
   {
    id: 'cg_3',
    title: 'Plant a Forest',
    description: 'For every 10km run by the community, we donate 1 tree.',
    currentValue: 8420,
    targetValue: 10000,
    unit: 'trees',
    participants: 18400,
    image: 'https://images.pexels.com/photos/1072179/pexels-photo-1072179.jpeg?auto=compress&cs=tinysrgb&w=800',
    color: 'from-green-600 to-emerald-600'
  },
  {
    id: 'cg_4',
    title: 'Mindful Minutes',
    description: 'Accumulate 500,000 minutes of meditation as a community.',
    currentValue: 125000,
    targetValue: 500000,
    unit: 'mins',
    participants: 6200,
    image: 'https://images.pexels.com/photos/1051838/pexels-photo-1051838.jpeg?auto=compress&cs=tinysrgb&w=800',
    color: 'from-purple-600 to-violet-600'
  }

];














 


