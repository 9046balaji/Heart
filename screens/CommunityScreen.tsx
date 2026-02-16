
import React, { useState, useEffect, useRef } from 'react';
import { communityFeed, challengesData, friendsData, communityGoals, CommunityPost, Friend, Challenge } from '../data/community';
import { useLanguage } from '../contexts/LanguageContext';
import { useToast } from '../components/Toast';

interface Comment {
  id: string;
  user: string;
  avatar: string;
  text: string;
  time: string;
}

interface ChatMessage {
  id: string;
  sender: 'me' | 'them' | 'system';
  user?: string; // For group chat
  avatar?: string;
  text: string;
  time: string;
}

// Mock Comments Data
const MOCK_COMMENTS: Record<string, Comment[]> = {
  'post_1': [
    { id: 'c1', user: 'Mike Ross', avatar: 'https://randomuser.me/api/portraits/men/11.jpg', text: 'Great pace! Keep it up.', time: '1h ago' },
    { id: 'c2', user: 'Sarah Connor', avatar: 'https://randomuser.me/api/portraits/women/68.jpg', text: 'Killing it! 🔥', time: '30m ago' }
  ]
};

// Mock Chat History
const MOCK_CHATS: Record<string, ChatMessage[]> = {};

const CommunityScreen: React.FC = () => {
  const { t } = useLanguage();
  const { showToast } = useToast();
  const [activeTab, setActiveTab] = useState<'Feed' | 'Challenges' | 'Friends'>('Feed');

  // Data State
  const [posts, setPosts] = useState<CommunityPost[]>(communityFeed);
  const [challenges, setChallenges] = useState<Challenge[]>(() => {
    const savedJoined = JSON.parse(localStorage.getItem('joined_challenges') || '[]') as string[];
    return challengesData.map(c => ({ ...c, joined: savedJoined.includes(c.id) }));
  });
  const [friends, setFriends] = useState<Friend[]>(friendsData);

  // Challenge Detail State
  const [selectedChallenge, setSelectedChallenge] = useState<Challenge | null>(null);
  const [challengeView, setChallengeView] = useState<'Feed' | 'Chat' | 'MyEntries'>('Feed');
  const [challengePosts, setChallengePosts] = useState<CommunityPost[]>([]);
  const [challengeChat, setChallengeChat] = useState<ChatMessage[]>([]);

  // Modal States
  const [showCreatePost, setShowCreatePost] = useState(false);
  const [isChallengeEntry, setIsChallengeEntry] = useState(false); // Context for create post
  const [activePostComments, setActivePostComments] = useState<string | null>(null); // Post ID
  const [activeChatFriend, setActiveChatFriend] = useState<Friend | null>(null);
  const [showInviteModal, setShowInviteModal] = useState(false);

  // Input States
  const [newPostText, setNewPostText] = useState('');
  const [newPostImage, setNewPostImage] = useState<string | null>(null);
  const [commentText, setCommentText] = useState('');
  const [chatText, setChatText] = useState('');
  const [friendSearch, setFriendSearch] = useState('');

  // Local Comments State (PostID -> Comments[])
  const [comments, setComments] = useState<Record<string, Comment[]>>(MOCK_COMMENTS);
  // Local Chats State (FriendID -> Messages[])
  const [chats, setChats] = useState<Record<string, ChatMessage[]>>(MOCK_CHATS);
  // Track liked posts
  const [likedPosts, setLikedPosts] = useState<Set<string>>(new Set());

  const fileInputRef = useRef<HTMLInputElement>(null);
  const chatScrollRef = useRef<HTMLDivElement>(null);
  const challengeChatScrollRef = useRef<HTMLDivElement>(null);

  // --- Feed Logic ---
  const handleLike = (postId: string, isChallengePost = false) => {
    const alreadyLiked = likedPosts.has(postId);
    const delta = alreadyLiked ? -1 : 1;

    setLikedPosts(prev => {
      const next = new Set(prev);
      if (alreadyLiked) next.delete(postId);
      else next.add(postId);
      return next;
    });

    if (isChallengePost) {
        setChallengePosts(prev => prev.map(p => p.id === postId ? { ...p, likes: Math.max(0, p.likes + delta) } : p));
    } else {
        setPosts(prev => prev.map(p => p.id === postId ? { ...p, likes: Math.max(0, p.likes + delta) } : p));
    }
  };

  const handleCreatePost = () => {
    if (!newPostText.trim() && !newPostImage) return;

    const newPost: CommunityPost = {
      id: `post_${Date.now()}`,
      user: {
        name: 'You',
        avatar: 'https://lh3.googleusercontent.com/aida-public/AB6AXuC8JJmFSNEDykVbLmg9GaDjI_y7oSrZg8hS9KI3YR7e3vQdQysk4FtU7xmAvLKhSuMQZgg2zbablylPhaXKCoy8vetGjpLe-Ty24fgpXbanV3G0gdxLOQp4UFEWDlaNETaNcWE1X-jhCKNT4bqUYPHtiTEZIBu24Ly5r-YP5vdBILXMcYIiLG6s8i1KztyEq0E4k79NTPODK1qXJhtVCURhe4x6JxRUzdlvshbonwupAWRLiXvZWsuODqHjdudOj9DAgtdsg0ScrbvE'
      },
      action: isChallengeEntry ? 'submitted an entry' : 'posted an update',
      timeAgo: 'Just now',
      content: newPostText,
      image: newPostImage || undefined,
      likes: 0,
      comments: 0
    };

    if (isChallengeEntry && selectedChallenge) {
        setChallengePosts([newPost, ...challengePosts]);
    } else {
        setPosts([newPost, ...posts]);
    }

    setShowCreatePost(false);
    setNewPostText('');
    setNewPostImage(null);
    setIsChallengeEntry(false);
  };

  const handleImageSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onloadend = () => {
        setNewPostImage(reader.result as string);
      };
      reader.readAsDataURL(file);
    }
  };

  // --- Comments Logic ---
  const handleAddComment = () => {
    if (!activePostComments || !commentText.trim()) return;

    const newComment: Comment = {
      id: `c_${Date.now()}`,
      user: 'You',
      avatar: 'https://lh3.googleusercontent.com/aida-public/AB6AXuC8JJmFSNEDykVbLmg9GaDjI_y7oSrZg8hS9KI3YR7e3vQdQysk4FtU7xmAvLKhSuMQZgg2zbablylPhaXKCoy8vetGjpLe-Ty24fgpXbanV3G0gdxLOQp4UFEWDlaNETaNcWE1X-jhCKNT4bqUYPHtiTEZIBu24Ly5r-YP5vdBILXMcYIiLG6s8i1KztyEq0E4k79NTPODK1qXJhtVCURhe4x6JxRUzdlvshbonwupAWRLiXvZWsuODqHjdudOj9DAgtdsg0ScrbvE',
      text: commentText,
      time: 'Just now'
    };

    setComments(prev => ({
      ...prev,
      [activePostComments]: [...(prev[activePostComments] || []), newComment]
    }));

    // Update post comment count (Check both feeds)
    setPosts(prev => prev.map(p => p.id === activePostComments ? { ...p, comments: p.comments + 1 } : p));
    setChallengePosts(prev => prev.map(p => p.id === activePostComments ? { ...p, comments: p.comments + 1 } : p));

    setCommentText('');
  };

  // --- Friends Logic ---
  const handleInvite = () => {
    const link = "https://cardioai.app/join/u123";
    if (navigator.share) {
      navigator.share({
        title: 'Join me on Cardio AI',
        text: selectedChallenge ? `Join the ${selectedChallenge.title} challenge with me!` : 'Let\'s get healthy together!',
        url: link
      });
    } else {
      navigator.clipboard.writeText(link);
      showToast("Invite link copied to clipboard!", 'success');
    }
    setShowInviteModal(false);
  };

  const handleSendFriendRequest = () => {
    if (!friendSearch.trim()) return;
    showToast(`Friend request sent to ${friendSearch}!`, 'success');
    setFriendSearch('');
  };

  // --- Chat Logic ---
  const handleChatSend = () => {
    if (!activeChatFriend || !chatText.trim()) return;

    const friendId = activeChatFriend.id;
    const msg: ChatMessage = {
      id: `msg_${Date.now()}`,
      sender: 'me',
      text: chatText,
      time: new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})
    };

    setChats(prev => ({
      ...prev,
      [friendId]: [...(prev[friendId] || []), msg]
    }));
    setChatText('');

    setTimeout(() => {
      const reply: ChatMessage = {
        id: `msg_${Date.now() + 1}`,
        sender: 'them',
        text: "That's awesome! Keep it up! 💪",
        time: new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})
      };
      setChats(prev => ({
        ...prev,
        [friendId]: [...(prev[friendId] || []), reply]
      }));
    }, 1500);
  };

  // --- Challenge Logic ---
  const openChallenge = (c: Challenge) => {
      // Get latest joined state from our tracked challenges
      const current = challenges.find(ch => ch.id === c.id) || c;
      setSelectedChallenge(current);
      // Initialize mock data for this challenge view
      setChallengePosts([
          {
              id: 'cp_1',
              user: { name: 'Alice Walker', avatar: 'https://randomuser.me/api/portraits/women/12.jpg' },
              action: 'completed day 5',
              timeAgo: '2h ago',
              content: 'Loving this challenge! feeling stronger every day.',
              image: 'https://images.pexels.com/photos/416778/pexels-photo-416778.jpeg?auto=compress&cs=tinysrgb&w=800',
              likes: 12,
              comments: 2
          },
          {
              id: 'cp_2',
              user: { name: 'Bob Harris', avatar: 'https://randomuser.me/api/portraits/men/45.jpg' },
              action: 'submitted entry',
              timeAgo: '5h ago',
              content: 'Here is my healthy meal for today!',
              image: 'https://images.pexels.com/photos/1640777/pexels-photo-1640777.jpeg?auto=compress&cs=tinysrgb&w=800',
              likes: 24,
              comments: 5
          }
      ]);
      setChallengeChat([
          { id: 'cm_1', sender: 'them', user: 'Coach Mike', avatar: 'https://randomuser.me/api/portraits/men/11.jpg', text: 'Welcome everyone! Let’s crush this week.', time: '09:00 AM' },
          { id: 'cm_2', sender: 'them', user: 'Sarah', avatar: 'https://randomuser.me/api/portraits/women/68.jpg', text: 'Ready to go! 🚀', time: '09:15 AM' }
      ]);
  };

  const handleChallengeChatSend = () => {
      if (!chatText.trim()) return;
      const msg: ChatMessage = {
          id: `cm_${Date.now()}`,
          sender: 'me',
          text: chatText,
          time: new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})
      };
      setChallengeChat(prev => [...prev, msg]);
      setChatText('');
  };

  const handleJoinChallenge = () => {
      if (!selectedChallenge) return;
      setChallenges(prev => prev.map(c => c.id === selectedChallenge.id ? {...c, joined: true} : c));
      setSelectedChallenge({...selectedChallenge, joined: true});
      // Persist joined challenges
      const savedJoined = JSON.parse(localStorage.getItem('joined_challenges') || '[]') as string[];
      if (!savedJoined.includes(selectedChallenge.id)) {
          localStorage.setItem('joined_challenges', JSON.stringify([...savedJoined, selectedChallenge.id]));
      }
  };

  useEffect(() => {
    if (chatScrollRef.current) {
      chatScrollRef.current.scrollTop = chatScrollRef.current.scrollHeight;
    }
    if (challengeChatScrollRef.current) {
        challengeChatScrollRef.current.scrollTop = challengeChatScrollRef.current.scrollHeight;
    }
  }, [chats, activeChatFriend, challengeChat]);

  // --- Renders ---

  const renderCreatePostModal = () => (
    <div className="fixed inset-0 z-[60] flex items-end sm:items-center justify-center bg-black/60 backdrop-blur-sm animate-in fade-in" onClick={() => setShowCreatePost(false)}>
      <div className="bg-white dark:bg-card-dark w-full sm:w-[500px] sm:rounded-2xl rounded-t-2xl p-4 shadow-2xl" onClick={e => e.stopPropagation()}>
        <div className="flex justify-between items-center mb-4">
          <h3 className="font-bold text-lg dark:text-white">{isChallengeEntry ? 'Submit Challenge Entry' : 'Create Post'}</h3>
          <button onClick={() => setShowCreatePost(false)}><span className="material-symbols-outlined text-slate-400">close</span></button>
        </div>

        <div className="flex gap-3 mb-4">
          <img src="https://lh3.googleusercontent.com/aida-public/AB6AXuC8JJmFSNEDykVbLmg9GaDjI_y7oSrZg8hS9KI3YR7e3vQdQysk4FtU7xmAvLKhSuMQZgg2zbablylPhaXKCoy8vetGjpLe-Ty24fgpXbanV3G0gdxLOQp4UFEWDlaNETaNcWE1X-jhCKNT4bqUYPHtiTEZIBu24Ly5r-YP5vdBILXMcYIiLG6s8i1KztyEq0E4k79NTPODK1qXJhtVCURhe4x6JxRUzdlvshbonwupAWRLiXvZWsuODqHjdudOj9DAgtdsg0ScrbvE" className="w-10 h-10 rounded-full object-cover" alt="Me" />
          <textarea
            className="flex-1 bg-slate-50 dark:bg-slate-800 rounded-xl p-3 resize-none border-none focus:ring-2 focus:ring-primary dark:text-white h-32"
            placeholder={isChallengeEntry ? "Describe your entry..." : "Share your progress or a thought..."}
            value={newPostText}
            onChange={e => setNewPostText(e.target.value)}
          ></textarea>
        </div>

        {newPostImage && (
          <div className="relative mb-4 rounded-xl overflow-hidden max-h-60">
            <img src={newPostImage} alt="Preview" className="w-full h-full object-cover" />
            <button
              onClick={() => setNewPostImage(null)}
              className="absolute top-2 right-2 w-8 h-8 bg-black/50 rounded-full flex items-center justify-center text-white"
            >
              <span className="material-symbols-outlined text-sm">close</span>
            </button>
          </div>
        )}

        <div className="flex justify-between items-center border-t border-slate-100 dark:border-slate-800 pt-3">
          <button onClick={() => fileInputRef.current?.click()} className="text-primary flex items-center gap-2 px-3 py-2 hover:bg-primary/10 rounded-lg transition-colors">
            <span className="material-symbols-outlined">image</span>
            <span className="font-bold text-sm">Photo</span>
          </button>
          <input type="file" ref={fileInputRef} className="hidden" accept="image/*" onChange={handleImageSelect} />

          <button
            onClick={handleCreatePost}
            disabled={!newPostText.trim() && !newPostImage}
            className="bg-primary hover:bg-primary-dark text-white px-6 py-2 rounded-lg font-bold disabled:opacity-50 transition-colors"
          >
            {isChallengeEntry ? 'Submit' : 'Post'}
          </button>
        </div>
      </div>
    </div>
  );

  const renderCommentsModal = () => {
    if (!activePostComments) return null;
    const postComments = comments[activePostComments] || [];

    return (
      <div className="fixed inset-0 z-[60] flex items-end justify-center bg-black/60 backdrop-blur-sm animate-in fade-in" onClick={() => setActivePostComments(null)}>
        <div className="bg-white dark:bg-card-dark w-full sm:w-[500px] h-[80vh] rounded-t-2xl flex flex-col shadow-2xl" onClick={e => e.stopPropagation()}>
          <div className="p-4 border-b border-slate-100 dark:border-slate-800 flex justify-between items-center">
            <h3 className="font-bold text-lg dark:text-white">Comments</h3>
            <button onClick={() => setActivePostComments(null)}><span className="material-symbols-outlined text-slate-400">close</span></button>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {postComments.length > 0 ? postComments.map(c => (
              <div key={c.id} className="flex gap-3">
                <img src={c.avatar} alt={c.user} className="w-8 h-8 rounded-full object-cover shrink-0" />
                <div className="bg-slate-50 dark:bg-slate-800/50 p-3 rounded-2xl rounded-tl-none">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-bold text-sm dark:text-white">{c.user}</span>
                    <span className="text-xs text-slate-400">{c.time}</span>
                  </div>
                  <p className="text-sm text-slate-600 dark:text-slate-300">{c.text}</p>
                </div>
              </div>
            )) : (
              <p className="text-center text-slate-400 text-sm py-10">No comments yet. Be the first!</p>
            )}
          </div>

          <div className="p-4 border-t border-slate-100 dark:border-slate-800 flex gap-2">
            <input
              type="text"
              placeholder="Add a comment..."
              value={commentText}
              onChange={e => setCommentText(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleAddComment()}
              className="flex-1 bg-slate-100 dark:bg-slate-800 border-none rounded-full px-4 text-sm focus:ring-2 focus:ring-primary dark:text-white"
            />
            <button
              onClick={handleAddComment}
              disabled={!commentText.trim()}
              className="w-10 h-10 bg-primary text-white rounded-full flex items-center justify-center disabled:opacity-50"
            >
              <span className="material-symbols-outlined text-sm">send</span>
            </button>
          </div>
        </div>
      </div>
    );
  };

  const renderChatModal = () => {
    if (!activeChatFriend) return null;
    const friendId = activeChatFriend.id;
    const messages = chats[friendId] || [];

    return (
      <div className="fixed inset-0 z-[60] bg-white dark:bg-card-dark flex flex-col animate-in slide-in-from-right duration-300">
        <div className="p-4 border-b border-slate-100 dark:border-slate-800 flex items-center gap-3 shadow-sm bg-white dark:bg-card-dark z-10">
          <button onClick={() => setActiveChatFriend(null)} className="text-slate-600 dark:text-slate-300"><span className="material-symbols-outlined">arrow_back</span></button>
          <div className="relative">
            <img src={activeChatFriend.avatar} alt={activeChatFriend.name} className="w-10 h-10 rounded-full object-cover" />
            <div className={`absolute bottom-0 right-0 w-2.5 h-2.5 rounded-full border-2 border-white dark:border-card-dark ${activeChatFriend.status === 'Online' ? 'bg-green-500' : 'bg-slate-400'}`}></div>
          </div>
          <div className="flex-1">
            <h3 className="font-bold dark:text-white leading-tight">{activeChatFriend.name}</h3>
            <p className="text-xs text-slate-500">{activeChatFriend.status}</p>
          </div>
          <button className="text-slate-400 hover:text-primary"><span className="material-symbols-outlined">videocam</span></button>
          <button className="text-slate-400 hover:text-primary"><span className="material-symbols-outlined">call</span></button>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-slate-50 dark:bg-[#0B1219]" ref={chatScrollRef}>
          <div className="text-center text-xs text-slate-400 my-4">Today</div>
          {messages.map(msg => (
            <div key={msg.id} className={`flex ${msg.sender === 'me' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-[75%] p-3 rounded-2xl text-sm ${
                msg.sender === 'me'
                ? 'bg-primary text-white rounded-br-none'
                : 'bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 rounded-bl-none shadow-sm'
              }`}>
                <p>{msg.text}</p>
                <p className={`text-[10px] text-right mt-1 ${msg.sender === 'me' ? 'text-white/70' : 'text-slate-400'}`}>{msg.time}</p>
              </div>
            </div>
          ))}
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full text-slate-400">
              <span className="material-symbols-outlined text-4xl mb-2 opacity-50">forum</span>
              <p className="text-sm">Start a conversation with {activeChatFriend.name}</p>
            </div>
          )}
        </div>

        <div className="p-3 border-t border-slate-100 dark:border-slate-800 bg-white dark:bg-card-dark flex gap-2 items-center">
          <button className="text-slate-400 hover:text-primary p-2"><span className="material-symbols-outlined">add_circle</span></button>
          <input
            type="text"
            placeholder="Message..."
            value={chatText}
            onChange={e => setChatText(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleChatSend()}
            className="flex-1 bg-slate-100 dark:bg-slate-800 border-none rounded-full px-4 py-2.5 text-sm focus:ring-2 focus:ring-primary dark:text-white"
          />
          <button
            onClick={handleChatSend}
            disabled={!chatText.trim()}
            className="w-10 h-10 bg-primary text-white rounded-full flex items-center justify-center disabled:opacity-50 hover:bg-primary-dark transition-colors"
          >
            <span className="material-symbols-outlined text-sm">send</span>
          </button>
        </div>
      </div>
    );
  };

  const renderPost = (post: CommunityPost) => (
    <div key={post.id} className="flex flex-col items-stretch justify-start rounded-xl shadow-sm bg-white dark:bg-card-dark border border-slate-100 dark:border-slate-800">
        <div className="flex items-center gap-3 p-4">
            <img className="h-10 w-10 rounded-full object-cover border border-slate-200 dark:border-slate-700" src={post.user.avatar} alt={post.user.name} />
            <div>
                <p className="text-slate-900 dark:text-white text-base font-bold leading-tight tracking-[-0.015em]">{post.user.name}</p>
                <p className="text-slate-500 dark:text-primary/70 text-sm font-normal leading-normal">{post.action} · {post.timeAgo}</p>
            </div>
        </div>
        {post.image && (
            <div className="w-full aspect-[2/1] bg-cover bg-center" style={{backgroundImage: `url("${post.image}")`}}></div>
        )}
        <div className="flex w-full grow flex-col items-stretch justify-center gap-2 p-4">
            <p className="text-slate-600 dark:text-primary/80 text-base font-normal leading-normal">{post.content}</p>
            {post.stats && (
                <div className="flex flex-wrap items-center gap-4 text-slate-500 dark:text-primary/70 text-sm pt-1">
                    {post.stats.map((stat, i) => (
                        <span key={i}><span className="font-bold text-slate-900 dark:text-white">{stat.value}</span> {stat.label}</span>
                    ))}
                </div>
            )}
        </div>
        <div className="flex items-center justify-start gap-1 p-4 pt-2 border-t border-slate-100 dark:border-slate-800/50">
            <button
                onClick={() => handleLike(post.id, selectedChallenge !== null)}
                className={`flex min-w-[48px] items-center justify-center rounded-lg h-10 px-3 gap-2 hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors ${likedPosts.has(post.id) ? 'text-red-500' : 'text-slate-500 dark:text-white'}`}
            >
                <span className={`material-symbols-outlined ${likedPosts.has(post.id) ? 'filled' : ''}`}>favorite</span>
                <span className="text-sm">{post.likes}</span>
            </button>
            <button
                onClick={() => setActivePostComments(post.id)}
                className="flex min-w-[48px] items-center justify-center rounded-lg h-10 px-3 text-slate-500 dark:text-white gap-2 hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors"
            >
                <span className="material-symbols-outlined">chat_bubble</span>
                <span className="text-sm">{post.comments}</span>
            </button>
            <button
                onClick={() => {
                    if (navigator.share) {
                        navigator.share({ title: post.user.name, text: post.content, url: window.location.href });
                    } else {
                        navigator.clipboard.writeText(post.content);
                        showToast('Post copied to clipboard!', 'success');
                    }
                }}
                className="flex min-w-[48px] items-center justify-center rounded-lg h-10 px-3 text-slate-500 dark:text-white gap-2 hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors ml-auto"
            >
                <span className="material-symbols-outlined">share</span>
            </button>
        </div>
    </div>
  );

  // --- Challenge Detail View ---
  if (selectedChallenge) {
      return (
          <div className="pb-24 animate-in slide-in-from-right duration-300 relative min-h-screen bg-background-light dark:bg-background-dark overflow-x-hidden">
              {/* Header */}
              <div className="relative h-48 bg-cover bg-center" style={{backgroundImage: `url("${selectedChallenge.image}")`}}>
                  <div className="absolute inset-0 bg-black/50"></div>
                  <div className="absolute top-0 left-0 right-0 p-4 flex justify-between items-center z-10">
                      <button onClick={() => setSelectedChallenge(null)} className="w-10 h-10 rounded-full bg-black/30 backdrop-blur-md flex items-center justify-center text-white hover:bg-black/50">
                          <span className="material-symbols-outlined">arrow_back</span>
                      </button>
                      <button onClick={() => setShowInviteModal(true)} className="w-10 h-10 rounded-full bg-black/30 backdrop-blur-md flex items-center justify-center text-white hover:bg-black/50">
                          <span className="material-symbols-outlined">person_add</span>
                      </button>
                  </div>
                  <div className="absolute bottom-4 left-4 right-4">
                      <h1 className="text-2xl font-bold text-white mb-1">{selectedChallenge.title}</h1>
                      <div className="flex items-center gap-2 text-white/80 text-xs">
                          <span className="bg-white/20 px-2 py-0.5 rounded">{selectedChallenge.participants}</span>
                          <span>• {selectedChallenge.timeLeft}</span>
                      </div>
                  </div>
              </div>

              {/* Action Bar */}
              <div className="p-4 bg-white dark:bg-card-dark border-b border-slate-100 dark:border-slate-800">
                  {!selectedChallenge.joined ? (
                      <button
                          onClick={handleJoinChallenge}
                          className="w-full py-3 bg-primary hover:bg-primary-dark text-white rounded-xl font-bold shadow-lg shadow-primary/20 transition-all"
                      >
                          Join Challenge
                      </button>
                  ) : (
                      <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2 text-green-600 dark:text-green-400">
                              <span className="material-symbols-outlined filled">check_circle</span>
                              <span className="font-bold text-sm">Joined</span>
                          </div>
                          <button onClick={() => { setIsChallengeEntry(true); setShowCreatePost(true); }} className="text-xs font-bold text-primary bg-primary/10 px-3 py-1.5 rounded-lg flex items-center gap-1 hover:bg-primary/20">
                              <span className="material-symbols-outlined text-sm">add_a_photo</span> Submit Entry
                          </button>
                      </div>
                  )}
              </div>

              {/* Tabs */}
              {selectedChallenge.joined && (
                  <>
                    <div className="flex border-b border-slate-200 dark:border-white/10 px-4">
                        {['Feed', 'Chat', 'MyEntries'].map(tab => (
                            <button
                                key={tab}
                                onClick={() => setChallengeView(tab as any)}
                                className={`flex-1 py-3 text-sm font-bold border-b-[3px] transition-colors ${
                                    challengeView === tab
                                    ? 'border-primary text-slate-900 dark:text-white'
                                    : 'border-transparent text-slate-500 dark:text-slate-400'
                                }`}
                            >
                                {tab === 'MyEntries' ? 'My Entries' : tab}
                            </button>
                        ))}
                    </div>

                    <div className="p-4 min-h-[400px]">
                        {challengeView === 'Feed' && (
                            <div className="flex flex-col gap-4">
                                {challengePosts.length > 0 ? challengePosts.map(renderPost) : (
                                    <div className="text-center py-10 text-slate-500">
                                        <p>No posts yet. Be the first to share your progress!</p>
                                    </div>
                                )}
                            </div>
                        )}

                        {challengeView === 'Chat' && (
                            <div className="flex flex-col h-[50vh] bg-slate-50 dark:bg-slate-900 rounded-xl overflow-hidden border border-slate-200 dark:border-slate-800">
                                <div className="flex-1 overflow-y-auto p-4 space-y-3" ref={challengeChatScrollRef}>
                                    {challengeChat.map(msg => (
                                        <div key={msg.id} className={`flex ${msg.sender === 'me' ? 'justify-end' : 'justify-start'}`}>
                                            {msg.sender !== 'me' && (
                                                <img src={msg.avatar} alt={msg.user} className="w-8 h-8 rounded-full mr-2 self-end" />
                                            )}
                                            <div className={`max-w-[75%] p-3 rounded-2xl text-sm ${
                                                msg.sender === 'me'
                                                ? 'bg-primary text-white rounded-br-none'
                                                : 'bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 rounded-bl-none shadow-sm'
                                            }`}>
                                                {msg.sender !== 'me' && <p className="text-[10px] text-primary font-bold mb-0.5">{msg.user}</p>}
                                                <p>{msg.text}</p>
                                                <p className={`text-[10px] text-right mt-1 opacity-70`}>{msg.time}</p>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                                <div className="p-2 bg-white dark:bg-card-dark border-t border-slate-200 dark:border-slate-800 flex gap-2">
                                    <input
                                        type="text"
                                        placeholder="Type a message..."
                                        value={chatText}
                                        onChange={e => setChatText(e.target.value)}
                                        onKeyDown={e => e.key === 'Enter' && handleChallengeChatSend()}
                                        className="flex-1 bg-slate-100 dark:bg-slate-800 border-none rounded-full px-4 text-sm focus:ring-2 focus:ring-primary dark:text-white"
                                    />
                                    <button onClick={handleChallengeChatSend} disabled={!chatText.trim()} className="w-10 h-10 bg-primary text-white rounded-full flex items-center justify-center disabled:opacity-50">
                                        <span className="material-symbols-outlined text-sm">send</span>
                                    </button>
                                </div>
                            </div>
                        )}

                        {challengeView === 'MyEntries' && (
                            <div>
                                <div className="bg-white dark:bg-card-dark p-4 rounded-xl shadow-sm border border-slate-100 dark:border-slate-800 mb-4">
                                    <h3 className="font-bold dark:text-white mb-2">Your Progress</h3>
                                    <div className="flex gap-4">
                                        <div className="flex-1 bg-slate-50 dark:bg-slate-800 p-3 rounded-lg text-center">
                                            <span className="block text-2xl font-bold text-primary">3</span>
                                            <span className="text-xs text-slate-500">Entries</span>
                                        </div>
                                        <div className="flex-1 bg-slate-50 dark:bg-slate-800 p-3 rounded-lg text-center">
                                            <span className="block text-2xl font-bold text-orange-500">12</span>
                                            <span className="text-xs text-slate-500">Likes</span>
                                        </div>
                                        <div className="flex-1 bg-slate-50 dark:bg-slate-800 p-3 rounded-lg text-center">
                                            <span className="block text-2xl font-bold text-green-500">Top 10%</span>
                                            <span className="text-xs text-slate-500">Rank</span>
                                        </div>
                                    </div>
                                </div>
                                <div className="grid grid-cols-2 gap-3">
                                    {challengePosts.filter(p => p.user.name === 'You').map(post => (
                                        <div key={post.id} className="rounded-xl overflow-hidden relative aspect-square bg-slate-200">
                                            {post.image ? (
                                                <img src={post.image} className="w-full h-full object-cover" alt="Entry" />
                                            ) : (
                                                <div className="w-full h-full flex items-center justify-center bg-slate-100 dark:bg-slate-800 p-2 text-xs text-center text-slate-500">
                                                    {post.content}
                                                </div>
                                            )}
                                            <div className="absolute bottom-0 left-0 right-0 bg-black/60 p-2 text-white text-xs flex justify-between">
                                                <span>{post.timeAgo}</span>
                                                <span className="flex items-center gap-1"><span className="material-symbols-outlined text-[10px]">favorite</span> {post.likes}</span>
                                            </div>
                                        </div>
                                    ))}
                                    <button
                                        onClick={() => { setIsChallengeEntry(true); setShowCreatePost(true); }}
                                        className="rounded-xl border-2 border-dashed border-slate-300 dark:border-slate-700 flex flex-col items-center justify-center text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors aspect-square"
                                    >
                                        <span className="material-symbols-outlined text-3xl mb-1">add_a_photo</span>
                                        <span className="text-xs font-bold">Add Entry</span>
                                    </button>
                                </div>
                            </div>
                        )}
                    </div>
                  </>
              )}

              {!selectedChallenge.joined && (
                  <div className="p-6 text-center text-slate-500 dark:text-slate-400">
                      <span className="material-symbols-outlined text-6xl opacity-20 mb-4">lock</span>
                      <p>Join this challenge to access the feed, chat, and track your progress!</p>
                  </div>
              )}

              {/* Modals reused from main screen */}
              {showCreatePost && renderCreatePostModal()}
              {activePostComments && renderCommentsModal()}
              {showInviteModal && (
                <div className="fixed inset-0 z-[70] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in" onClick={() => setShowInviteModal(false)}>
                    <div className="bg-white dark:bg-card-dark rounded-2xl p-6 w-full max-w-sm text-center shadow-xl" onClick={e => e.stopPropagation()}>
                        <div className="w-16 h-16 bg-blue-100 dark:bg-blue-900/30 rounded-full flex items-center justify-center mx-auto mb-4 text-blue-600 dark:text-blue-400">
                            <span className="material-symbols-outlined text-3xl">share</span>
                        </div>
                        <h3 className="font-bold text-lg dark:text-white mb-2">Invite to Challenge</h3>
                        <p className="text-slate-500 text-sm mb-6">Share the link to '{selectedChallenge.title}' with your friends.</p>
                        <button onClick={handleInvite} className="w-full py-3 bg-primary text-white font-bold rounded-xl shadow-lg shadow-primary/20 hover:bg-primary-dark transition-colors">
                            Share Link
                        </button>
                    </div>
                </div>
              )}
          </div>
      );
  }

  return (
    <div className="pb-24 animate-in fade-in slide-in-from-bottom-4 duration-300 relative min-h-screen overflow-x-hidden">
        {/* Internal Tabs */}
        <div className="bg-background-light dark:bg-background-dark">
            <div className="flex border-b border-slate-200 dark:border-white/10 px-4 justify-between">
                {['Feed', 'Challenges', 'Friends'].map(tab => (
                    <button
                        key={tab}
                        onClick={() => setActiveTab(tab as any)}
                        className={`flex flex-col items-center justify-center border-b-[3px] pb-3 pt-4 flex-1 transition-colors ${
                            activeTab === tab
                            ? 'border-primary text-slate-900 dark:text-white'
                            : 'border-transparent text-slate-500 dark:text-slate-400'
                        }`}
                    >
                        <p className="text-sm font-bold leading-normal tracking-[0.015em]">{tab}</p>
                    </button>
                ))}
            </div>
        </div>

        {activeTab === 'Feed' && (
            <>
                {/* Community Goals Section (Co-op) */}
                <div className="px-4 pt-5 pb-3">
                    <h2 className="text-slate-900 dark:text-white text-[22px] font-bold leading-tight tracking-[-0.015em] mb-3">Community Goals</h2>
                    <div className="flex overflow-x-auto no-scrollbar gap-3 snap-x">
                        {communityGoals.map((goal, idx) => {
                            const progress = (goal.currentValue / goal.targetValue) * 100;
                            return (
                                <div key={idx} className={`flex-none w-[300px] snap-center rounded-2xl bg-gradient-to-br ${goal.color} text-white p-4 shadow-lg relative overflow-hidden`}>
                                    <div className="absolute top-0 right-0 w-32 h-32 bg-white/10 rounded-full -mr-10 -mt-10 blur-2xl"></div>
                                    <div className="relative z-10">
                                        <div className="flex justify-between items-start mb-4">
                                            <div>
                                                <h3 className="font-bold text-lg leading-tight">{goal.title}</h3>
                                                <p className="text-xs text-white/80 mt-1">{goal.participants.toLocaleString()} contributors</p>
                                            </div>
                                            <div className="w-10 h-10 bg-white/20 backdrop-blur-sm rounded-full flex items-center justify-center">
                                                <span className="material-symbols-outlined filled">groups</span>
                                            </div>
                                        </div>

                                        <div className="mb-2">
                                            <div className="flex justify-between text-xs font-bold mb-1 opacity-90">
                                                <span>{goal.currentValue.toLocaleString()}</span>
                                                <span>{goal.targetValue.toLocaleString()} {goal.unit}</span>
                                            </div>
                                            <div className="w-full bg-black/20 rounded-full h-2 overflow-hidden">
                                                <div className="bg-white h-full rounded-full transition-all duration-1000" style={{width: `${progress}%`}}></div>
                                            </div>
                                        </div>

                                        <button className="w-full py-2 bg-white/20 hover:bg-white/30 rounded-lg text-xs font-bold transition-colors flex items-center justify-center gap-1 backdrop-blur-md">
                                            <span className="material-symbols-outlined text-sm">add_circle</span> Contribute
                                        </button>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>

                {/* Section Header: Feed */}
                <h2 className="text-slate-900 dark:text-white text-[22px] font-bold leading-tight tracking-[-0.015em] px-4 pb-3 pt-5">Activity Feed</h2>

                <div className="flex flex-col gap-4 px-4 @container">
                    {posts.map(renderPost)}
                </div>
            </>
        )}

        {activeTab === 'Challenges' && (
            <div className="flex flex-col gap-4 px-4 py-4">
                {challenges.map(challenge => (
                    <div
                        key={challenge.id}
                        onClick={() => openChallenge(challenge)}
                        className="bg-white dark:bg-card-dark rounded-xl overflow-hidden shadow-sm border border-slate-100 dark:border-slate-800 cursor-pointer hover:shadow-md transition-all"
                    >
                        <div className="h-32 bg-cover bg-center relative" style={{backgroundImage: `url("${challenge.image}")`}}>
                            <div className="absolute inset-0 bg-black/40 flex items-center justify-center">
                                <h3 className="text-white text-xl font-bold text-center px-4">{challenge.title}</h3>
                            </div>
                        </div>
                        <div className="p-4">
                            <div className="flex justify-between items-start mb-2">
                                <span className="text-xs font-bold bg-primary/20 text-primary px-2 py-1 rounded">{challenge.timeLeft}</span>
                                <span className="text-xs text-slate-500">{challenge.participants}</span>
                            </div>
                            <p className="text-slate-600 dark:text-slate-300 text-sm mb-4 line-clamp-2">{challenge.description}</p>
                            <button
                                className={`w-full py-3 rounded-xl font-bold transition-colors ${challenge.joined ? 'bg-green-100 dark:bg-green-900/30 text-green-600 dark:text-green-400' : 'bg-primary text-slate-900 hover:bg-primary-dark'}`}
                            >
                                {challenge.joined ? 'View Challenge' : 'Join Challenge'}
                            </button>
                        </div>
                    </div>
                ))}
            </div>
        )}

        {activeTab === 'Friends' && (
            <div className="flex flex-col gap-2 px-4 py-4">
                {/* Invite & Add Section */}
                <div className="flex gap-3 mb-4">
                    <button
                        onClick={() => setShowInviteModal(true)}
                        className="flex-1 py-3 border-2 border-dashed border-slate-300 dark:border-slate-700 rounded-xl text-slate-500 font-bold flex items-center justify-center gap-2 hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors"
                    >
                        <span className="material-symbols-outlined">share</span>
                        Invite Link
                    </button>
                    <div className="flex-1 relative">
                        <input
                            type="text"
                            placeholder="Add friend..."
                            value={friendSearch}
                            onChange={e => setFriendSearch(e.target.value)}
                            onKeyDown={e => e.key === 'Enter' && handleSendFriendRequest()}
                            className="w-full h-full pl-4 pr-10 rounded-xl bg-white dark:bg-card-dark border border-slate-200 dark:border-slate-700 text-sm focus:outline-none focus:border-primary"
                        />
                        <button
                            onClick={handleSendFriendRequest}
                            className="absolute right-2 top-1/2 -translate-y-1/2 text-primary p-1"
                        >
                            <span className="material-symbols-outlined text-lg">person_add</span>
                        </button>
                    </div>
                </div>

                {friends.map(friend => {
                    const needsNudge = friend.status === 'Offline' && (friend.lastActive.includes('d') || (friend.lastActive.includes('h') && parseInt(friend.lastActive) > 2));

                    return (
                        <div key={friend.id} className="flex items-center justify-between p-4 bg-white dark:bg-card-dark rounded-xl shadow-sm border border-slate-100 dark:border-slate-800">
                            <div className="flex items-center gap-3">
                                <div className="relative">
                                    <img src={friend.avatar} alt={friend.name} className="w-12 h-12 rounded-full object-cover" />
                                    <div className={`absolute bottom-0 right-0 w-3 h-3 rounded-full border-2 border-white dark:border-card-dark ${
                                        friend.status === 'Online' ? 'bg-green-500' :
                                        friend.status === 'In a Workout' ? 'bg-purple-500' : 'bg-slate-400'
                                    }`}></div>
                                </div>
                                <div>
                                    <h4 className="font-bold dark:text-white">{friend.name}</h4>
                                    <p className="text-xs text-slate-500">{friend.status === 'Offline' ? `Active ${friend.lastActive}` : friend.status}</p>
                                </div>
                            </div>
                            <div className="flex items-center gap-3">
                                {friend.streak > 0 && (
                                    <div className="flex items-center gap-1 text-orange-500 bg-orange-50 dark:bg-orange-900/20 px-2 py-1 rounded-lg">
                                        <span className="material-symbols-outlined text-sm filled">local_fire_department</span>
                                        <span className="text-xs font-bold">{friend.streak}</span>
                                    </div>
                                )}

                                <button
                                    onClick={() => setActiveChatFriend(friend)}
                                    className="w-10 h-10 rounded-full bg-blue-50 dark:bg-blue-900/20 flex items-center justify-center text-blue-600 dark:text-blue-400 hover:bg-blue-100 dark:hover:bg-blue-900/40 transition-colors"
                                    title="Chat"
                                >
                                    <span className="material-symbols-outlined text-xl">chat</span>
                                </button>
                            </div>
                        </div>
                    );
                })}
            </div>
        )}

        {/* Floating Action Button for Create Post */}
        {activeTab === 'Feed' && (
            <div className="fixed bottom-24 right-6 z-20">
                <button
                    onClick={() => setShowCreatePost(true)}
                    className="flex h-14 w-14 cursor-pointer items-center justify-center overflow-hidden rounded-full bg-primary text-slate-900 shadow-lg hover:scale-105 transition-transform"
                >
                    <span className="material-symbols-outlined !text-3xl">add_a_photo</span>
                </button>
            </div>
        )}

        {/* Modals */}
        {showCreatePost && renderCreatePostModal()}
        {activePostComments && renderCommentsModal()}
        {activeChatFriend && renderChatModal()}

        {/* Invite Modal */}
        {showInviteModal && (
            <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in" onClick={() => setShowInviteModal(false)}>
                <div className="bg-white dark:bg-card-dark rounded-2xl p-6 w-full max-w-sm text-center shadow-xl" onClick={e => e.stopPropagation()}>
                    <div className="w-16 h-16 bg-blue-100 dark:bg-blue-900/30 rounded-full flex items-center justify-center mx-auto mb-4 text-blue-600 dark:text-blue-400">
                        <span className="material-symbols-outlined text-3xl">share</span>
                    </div>
                    <h3 className="font-bold text-lg dark:text-white mb-2">Invite Friends</h3>
                    <p className="text-slate-500 text-sm mb-6">Share your unique link to connect with friends on Cardio AI.</p>
                    <button onClick={handleInvite} className="w-full py-3 bg-primary text-white font-bold rounded-xl shadow-lg shadow-primary/20 hover:bg-primary-dark transition-colors">
                        Share Link
                    </button>
                </div>
            </div>
        )}
    </div>
  );
};

export default CommunityScreen;
